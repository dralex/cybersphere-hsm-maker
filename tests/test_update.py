# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the update loop and of its command options
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

import CyberiadaML
from conftest import FakeClient, chat_answer, diagram, fenced
import hsm_maker
from hsm_maker import builder as B
from hsm_maker import cli
from hsm_maker import maker as M
from hsm_maker import notation as N
from hsm_maker.language import Texts

CHANGE = 'Add a maintenance mode entered by SERVICE from Idle'


def drawn():
    tree = N.parse(diagram('lift.hsm'))
    N.analyze(tree)
    return B.encode(B.build(tree))


LIFT = drawn()
OLD = M.Original(LIFT)
CHANGED = OLD.notation.replace(
    '    CALL [call_floor == floor] -> DoorsOpen\n',
    '    CALL [call_floor == floor] -> DoorsOpen\n    SERVICE -> Maintenance\n') + \
    '  state Maintenance\n    SERVICE_DONE -> Idle\n'
WRONG = OLD.notation.replace('    CALL [call_floor == floor] -> DoorsOpen\n',
                             '    SERVICE -> Maintenance\n')


def test_run_update():
    client = FakeClient([fenced(WRONG), fenced(CHANGED)])
    result = M.run_update(LIFT, CHANGE, client)
    assert (result.ok, result.rounds, result.language) == (True, 2, 'en')
    assert sorted(c.code for c in result.changes) == ['C01', 'C06', 'C06']
    first = client.calls[0][1][0]['content']
    assert first == Texts('en').text('update_request', diagram=OLD.notation,
                                     change=CHANGE)
    feedback = client.calls[1][1][2]['content']
    assert "unknown target 'Maintenance'" in feedback
    document = CyberiadaML.Document()
    document.decode(result.graphml, strict=True)


def test_update_entry():
    result = hsm_maker.update(LIFT, 'Добавь режим обслуживания',
                              FakeClient([fenced(CHANGED)]))
    assert result.ok and result.language == 'ru'


def test_render_option(tmp_path, capfd):
    path = tmp_path / 'lift.graphml'
    path.write_text(LIFT, encoding='utf-8')
    assert cli.main(['--render', str(path)]) == cli.EXIT_MADE
    assert capfd.readouterr().out == OLD.notation


def test_offline_update(tmp_path):
    original = tmp_path / 'lift.graphml'
    original.write_text(LIFT, encoding='utf-8')
    notation = tmp_path / 'changed.hsm'
    notation.write_text(CHANGED, encoding='utf-8')
    out = tmp_path / 'out.graphml'
    report = tmp_path / 'diagnostics.json'
    assert cli.main(['--update', str(original), '--notation', str(notation),
                     '-o', str(out), '--diagnostics', str(report)]) == \
        cli.EXIT_MADE
    entries = json.loads(report.read_text(encoding='utf-8'))
    assert sorted(e['rule'] for e in entries) == ['C01', 'C06', 'C06']
    added = [e for e in entries if e['rule'] == 'C01'][0]
    assert added == {'severity': 'info', 'rule': 'C01',
                     'message': "added state 'Maintenance'",
                     'element': added['element']}
    document = CyberiadaML.Document()
    document.decode(out.read_text(encoding='utf-8'), strict=True)
    assert document.find_element_by_id(added['element']).get_name() == \
        'Maintenance'


def test_update_by_the_model(stub, tmp_path, capsys):
    original = tmp_path / 'lift.graphml'
    original.write_text(LIFT, encoding='utf-8')
    stub.answer(chat_answer(fenced(CHANGED)))
    out = tmp_path / 'out.graphml'
    assert cli.main(['--url', stub.url, '--model', 'm', '--update',
                     str(original), '-o', str(out), CHANGE]) == cli.EXIT_MADE
    assert 'rounds: 1' in capsys.readouterr().err
    assert CHANGE in stub.requests[0][2]['messages'][1]['content']
    assert 'Maintenance' in out.read_text(encoding='utf-8')


def test_empty_update_file_is_a_new_diagram(tmp_path):
    empty = tmp_path / 'empty.graphml'
    empty.write_text('', encoding='utf-8')
    notation = tmp_path / 'lift.hsm'
    notation.write_text(diagram('lift.hsm'), encoding='utf-8')
    out = tmp_path / 'out.graphml'
    assert cli.main(['--update', str(empty), '--notation', str(notation),
                     '-o', str(out)]) == cli.EXIT_MADE
    assert 'geometry/ full' in out.read_text(encoding='utf-8')


def test_refused_diagram(tmp_path, capsys):
    document = CyberiadaML.Document()
    machine = document.new_state_machine('M')
    document.new_initial(machine)
    document.new_state(machine, 'A')
    path = tmp_path / 'refused.graphml'
    path.write_text(document.encode(), encoding='utf-8')
    assert cli.main(['--render', str(path)]) == cli.EXIT_USAGE
    assert 'needs one transition' in capsys.readouterr().err


def test_failed_change_diagnostics(tmp_path):
    original = tmp_path / 'lift.graphml'
    original.write_text(LIFT, encoding='utf-8')
    notation = tmp_path / 'wrong.hsm'
    notation.write_text(WRONG, encoding='utf-8')
    report = tmp_path / 'diagnostics.json'
    assert cli.main(['--update', str(original), '--notation', str(notation),
                     '--diagnostics', str(report)]) == cli.EXIT_NOT_MADE
    entries = json.loads(report.read_text(encoding='utf-8'))
    assert [(e['severity'], e['rule']) for e in entries] == [('error', 'R01')]
