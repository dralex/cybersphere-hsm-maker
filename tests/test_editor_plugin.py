# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the plugin of CyberiadaHSM-Editor
#
#  Copyright (C) 2026 Alexey Fedoseev <aleksey@fedoseev.net>
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program. If not, see https://www.gnu.org/licenses/
#
#  -----------------------------------------------------------------------------

import json
import os
import re
import subprocess
import sys

import pytest

import CyberiadaML
from conftest import ROOT, chat_answer, diagram, fenced
from hsm_maker import __version__, cli
from hsm_maker import maker as M
from hsm_maker import plugin as P

PLUGIN = os.path.join(ROOT, 'editor-plugin', 'plugin.json')
EDITOR = os.path.join(os.path.dirname(ROOT), 'CyberiadaHSM-Editor', 'build',
                      'CyberiadaEditor')
RESULTS = ('replace', 'new-document', 'diagnostics', 'files', 'log')
VARIABLE_RE = re.compile(r'\$\{([a-z_-]+)(?::([a-z_]+))?\}')
VARIABLES = ('input', 'output', 'diagnostics', 'outdir', 'rundir',
             'plugin_dir', 'request', 'param', 'param-file', 'meta',
             'selection', 'document', 'document_dir', 'document_name')
TIMEOUT = 120


def descriptor():
    with open(PLUGIN, encoding='utf-8') as source:
        return json.load(source)


def test_descriptor():
    plugin = descriptor()
    assert (plugin['api'], plugin['id']) == (1, 'hsm-maker')
    parameters = {p['id']: p for p in plugin['parameters']}
    assert parameters['key']['type'] == 'secret'
    for action in plugin['actions']:
        assert action['result'] in RESULTS
        assert set(action['parameters']) <= set(parameters)
        for argument in action['argv']:
            for name, param in VARIABLE_RE.findall(argument):
                assert name in VARIABLES, argument
                if name.startswith('param'):
                    assert param in action['parameters'], argument
                    assert parameters[param]['type'] != 'secret'
    for icon in [plugin['icon']] + [a['icon'] for a in plugin['actions']
                                    if 'icon' in a]:
        assert os.path.isfile(os.path.join(ROOT, 'editor-plugin', icon))


def editor(arguments, tmp_path, key=None, installed=False):
    """The editor batch with the plugin of the repository, or with the
    installed plugins of its user folder (XDG_DATA_HOME under tmp_path) and
    no Python of this run on PATH."""
    if not os.access(EDITOR, os.X_OK):
        pytest.skip('CyberiadaEditor is not built beside the repository')
    environment = dict(os.environ)
    environment.update({
        'QT_QPA_PLATFORM': 'offscreen',
        'XDG_CONFIG_HOME': str(tmp_path / 'config'),
        'XDG_DATA_HOME': str(tmp_path / 'data'),
        'CYBERIADA_EDITOR_PLUGIN_PATH': '',
    })
    if installed:
        environment.pop('PYTHONPATH', None)
    else:
        environment['PATH'] = os.path.dirname(sys.executable) + \
            os.pathsep + environment.get('PATH', '')
        environment['PYTHONPATH'] = ROOT
        arguments = arguments + ['--plugin-path', ROOT]
    if key:
        environment['STUB_KEY'] = key
    return subprocess.run([EDITOR, '--batch'] + arguments, env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=TIMEOUT, check=False,
                          universal_newlines=True)


def model(stub):
    return ['--plugin-param', 'url=' + stub.url, '--plugin-param', 'model=m',
            '--plugin-param', 'key=env:STUB_KEY']


def test_listed(tmp_path):
    run = editor(['--list-plugins'], tmp_path)
    assert 'hsm-maker 0.1.0 enabled' in run.stdout


def test_draw_and_change(stub, tmp_path):
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('A lift with one call button on every floor',
                      encoding='utf-8')
    stub.answer(chat_answer(fenced(diagram('lift.hsm'))))
    drawn = tmp_path / 'lift.graphml'
    run = editor(['--run-plugin', 'hsm-maker:draw', '--plugin-param',
                  'prompt=@' + str(prompt)] + model(stub) +
                 ['--save', str(drawn), '--dump-plugin'], tmp_path, 'k')
    assert run.returncode == 0, run.stdout + run.stderr
    assert stub.requests[0][1]['authorization'] == 'Bearer k'
    text = drawn.read_text(encoding='utf-8')
    assert 'Lift' in text

    old = M.Original(text)
    changed = old.notation.replace(
        '    CALL [call_floor == floor] -> DoorsOpen\n',
        '    CALL [call_floor == floor] -> DoorsOpen\n'
        '    SERVICE -> Maintenance\n') + \
        '  state Maintenance\n    SERVICE_DONE -> Idle\n'
    stub.answer(chat_answer(fenced(changed)))
    request = tmp_path / 'change.txt'
    request.write_text('Add a maintenance mode', encoding='utf-8')
    result = tmp_path / 'changed.graphml'
    run = editor([str(drawn), '--run-plugin', 'hsm-maker:change',
                  '--plugin-param', 'change=@' + str(request)] + model(stub) +
                 ['--save', str(result), '--dump-plugin'], tmp_path, 'k')
    assert run.returncode == 0, run.stdout + run.stderr
    assert "added state 'Maintenance'" in run.stdout
    before = CyberiadaML.Document()
    before.decode(text)
    after = CyberiadaML.Document()
    after.decode(result.read_text(encoding='utf-8'))
    for vertex in old.tree.walk():
        if vertex.kind != 'initial':
            assert after.find_element_by_id(vertex.element_id) is not None


def test_notation(tmp_path):
    drawn = tmp_path / 'lift.graphml'
    with open(os.path.join(ROOT, 'tests', 'good', 'lift.graphml'),
              encoding='utf-8') as source:
        drawn.write_text(source.read(), encoding='utf-8')
    run = editor([str(drawn), '--run-plugin', 'hsm-maker:notation',
                  '--dump-plugin'], tmp_path)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'machine Lift' in run.stdout


def test_version():
    assert descriptor()['version'] == __version__


def test_user_folder():
    tail = os.path.join('Cyberiada', 'Cyberiada State Machine Editor',
                        'plugins')
    assert P.user_folder({'XDG_DATA_HOME': '/x', 'HOME': '/h'}, 'Linux') == \
        os.path.join('/x', tail)
    assert P.user_folder({'HOME': '/h'}, 'Linux') == \
        os.path.join('/h', '.local', 'share', tail)
    assert P.user_folder({'APPDATA': 'C:/R', 'HOME': '/h'}, 'Windows') == \
        os.path.join('C:/R', tail)
    assert P.user_folder({'HOME': '/h'}, 'Darwin') == \
        os.path.join('/h', 'Library', 'Application Support', tail)


def test_install_pins_the_python(tmp_path):
    assert P.source() == os.path.join(ROOT, 'editor-plugin')
    folder = P.install(str(tmp_path), executable='/opt/py/bin/python')
    assert folder == str(tmp_path / 'hsm-maker')
    with open(os.path.join(folder, 'plugin.json'), encoding='utf-8') as file:
        installed = json.load(file)
    original = descriptor()
    assert 'interpreter' not in installed
    assert [a['argv'] for a in installed['actions']] == \
        [['/opt/py/bin/python'] + a['argv'] for a in original['actions']]
    assert installed['env'] == dict(original['env'], PYTHONPATH=ROOT)
    for name in ('README.md', 'icons/draw.svg', 'icons/change.svg'):
        assert os.path.isfile(os.path.join(folder, name))


def test_install_replaces_only_the_plugin(tmp_path):
    folder = P.install(str(tmp_path))
    (tmp_path / 'hsm-maker' / 'stale.txt').write_text('x', encoding='utf-8')
    assert P.install(str(tmp_path)) == folder
    assert not os.path.exists(os.path.join(folder, 'stale.txt'))
    other = tmp_path / 'other'
    (other / 'hsm-maker').mkdir(parents=True)
    (other / 'hsm-maker' / 'keep.txt').write_text('x', encoding='utf-8')
    with pytest.raises(P.PluginError):
        P.install(str(other))
    assert (other / 'hsm-maker' / 'keep.txt').exists()


def test_install_command(tmp_path, capsys):
    assert cli.main(['--install-editor-plugin', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert str(tmp_path / 'hsm-maker') in out and sys.executable in out
    (tmp_path / 'x' / 'hsm-maker').mkdir(parents=True)
    assert cli.main(['--install-editor-plugin', str(tmp_path / 'x')]) == 2


def test_installed_plugin_runs(tmp_path):
    folder = P.install(P.user_folder({'XDG_DATA_HOME': str(tmp_path / 'data')},
                                     'Linux'))
    assert folder.startswith(str(tmp_path / 'data'))
    run = editor(['--list-plugins'], tmp_path, installed=True)
    assert 'hsm-maker {} enabled'.format(__version__) in run.stdout, \
        run.stdout + run.stderr
    drawn = tmp_path / 'lift.graphml'
    with open(os.path.join(ROOT, 'tests', 'good', 'lift.graphml'),
              encoding='utf-8') as good:
        drawn.write_text(good.read(), encoding='utf-8')
    run = editor([str(drawn), '--run-plugin', 'hsm-maker:notation',
                  '--dump-plugin'], tmp_path, installed=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'machine Lift' in run.stdout
