# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the code language: the language: header, the option
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

import pytest

from hsm_maker.cyberiadaml import CyberiadaML
from conftest import ROOT, FakeClient, diagram, fenced
from hsm_maker import cli
from hsm_maker import maker as M
from hsm_maker import notation as N
from hsm_maker.builder import PLATFORM_LANGUAGE
from hsm_maker.language import AUTO, Texts

SMALL = 'machine M\n  initial -> A\n  state A\n    entry/ go()\n'
PROMPT = 'A lift with one call button on every floor'


def language_of(graphml):
    document = CyberiadaML.Document()
    document.decode(graphml)
    return document.meta().get_string(PLATFORM_LANGUAGE)


def with_language(language, text=SMALL):
    return 'language: ' + language + '\n' + text if language else text


def drawn(language):
    """A diagram with the code language written as it is."""
    conversion = M.convert(SMALL)
    document = CyberiadaML.Document()
    document.decode(conversion.graphml)
    if language:
        document.meta().set_string(PLATFORM_LANGUAGE, language)
    return document.encode()


def test_header():
    tree = N.parse('name: L\ndescription: D\nlanguage: python\n' + SMALL)
    assert tree.language == 'Python'
    assert N.parse(with_language('Lua')).language == 'Lua'
    assert N.parse(SMALL).language is None
    assert N.render(tree).startswith(
        'name: L\ndescription: D\nlanguage: Python\nmachine M\n')


@pytest.mark.parametrize('text, expected', [
    ('language: C\nlanguage: C\n' + SMALL, [('N27', 2)]),
    (SMALL + 'language: C\n', [('N27', 5)]),
    ('language:\n' + SMALL, [('N28', 1)]),
])
def test_header_issues(text, expected):
    with pytest.raises(N.NotationError) as error:
        N.parse(text)
    assert [(i.code, i.line) for i in error.value.issues] == expected


def test_spelling():
    assert [N.language_spelling(n) for n in
            ('c++', 'JAVASCRIPT', 'c#', 'python3', None)] == \
        ['C++', 'JavaScript', 'C#', 'python3', None]


def test_built_and_read_back():
    conversion = M.convert(with_language('C++'))
    assert conversion.ok
    assert language_of(conversion.graphml) == 'C++'
    notation = M.Original(conversion.graphml).notation
    assert notation.startswith('language: C++\nmachine M\n')
    assert 'note: platformLanguage' not in notation
    assert language_of(M.convert(SMALL).graphml) == ''


def test_chosen_replaces_the_header():
    assert language_of(M.convert(with_language('C'), code_language='python')
                       .graphml) == 'Python'
    assert language_of(M.convert(SMALL, code_language='Java').graphml) == \
        'Java'
    assert language_of(M.convert(with_language('C'), code_language=AUTO)
                       .graphml) == 'C'


def test_run_declared_by_the_model():
    client = FakeClient([fenced(with_language('Python', diagram('lift.hsm')))])
    result = M.run(PROMPT, client)
    assert result.ok
    assert language_of(result.graphml) == 'Python'
    assert client.calls[0][1] == [{'role': 'user', 'content': PROMPT}]


def test_run_tells_the_model():
    client = FakeClient([fenced(with_language('Python', diagram('lift.hsm')))])
    result = M.run(PROMPT, client, code_language='C++')
    assert result.ok
    assert language_of(result.graphml) == 'C++'
    assert client.calls[0][1][0]['content'] == PROMPT + '\n\n' + \
        Texts('en').text('code_language', language='C++')


@pytest.mark.parametrize('old, header, expected', [
    ('Python', None, 'Python'),
    ('Python', 'C++', 'C++'),
    ('python', 'python', 'python'),
    ('', None, ''),
    ('', 'C', 'C'),
])
def test_change(old, header, expected):
    graphml = drawn(old)
    original = M.Original(graphml)
    assert original.notation.startswith(
        'language: ' + old + '\n' if old else 'machine M\n')
    conversion = M.change(graphml, with_language(header))
    assert conversion.ok
    assert language_of(conversion.graphml) == expected


def test_run_update_tells_the_model():
    graphml = drawn('Python')
    client = FakeClient([fenced(SMALL)])
    result = M.run_update(graphml, 'Rename nothing', client,
                          code_language='C')
    assert result.ok
    assert language_of(result.graphml) == 'C'
    assert client.calls[0][1][0]['content'].endswith(
        Texts('en').text('code_language', language='C'))


def test_command(tmp_path, monkeypatch):
    notation = tmp_path / 'small.hsm'
    notation.write_text(with_language('C'), encoding='utf-8')
    out = tmp_path / 'small.graphml'
    arguments = ['--notation', str(notation), '-o', str(out)]
    assert cli.main(arguments + ['--code-language', 'java']) == cli.EXIT_MADE
    assert language_of(out.read_text(encoding='utf-8')) == 'Java'
    monkeypatch.setenv(cli.ENV_CODE_LANGUAGE, 'Python')
    assert cli.main(arguments) == cli.EXIT_MADE
    assert language_of(out.read_text(encoding='utf-8')) == 'Python'
    assert cli.main(arguments + ['--code-language', 'auto']) == cli.EXIT_MADE
    assert language_of(out.read_text(encoding='utf-8')) == 'C'


def test_plugin_setting():
    with open(os.path.join(ROOT, 'editor-plugin', 'plugin.json'),
              encoding='utf-8') as source:
        plugin = json.load(source)
    parameters = {p['id']: p for p in plugin['parameters']}
    setting = parameters['code_language']
    assert (setting['scope'], setting['default']) == ('persistent', AUTO)
    assert setting['choices'] == [AUTO] + list(N.CODE_LANGUAGES)
    for action in plugin['actions']:
        if action['id'] in ('draw', 'change'):
            assert 'code_language' in action['parameters']
            option = action['argv'].index('--code-language')
            assert action['argv'][option + 1] == '${param:code_language}'
