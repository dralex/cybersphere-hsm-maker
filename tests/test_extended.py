# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the points, the submachines, the history and the propagation
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

import os

import pytest

import CyberiadaML
from conftest import GOOD, diagram, validate
from hsm_maker import builder as B
from hsm_maker import notation as N

REGEN = os.environ.get('REGEN')


def vertex(tree, path, machine=0):
    return [v for v in tree.machines[machine].walk() if v.path == path][0]


def issues(text):
    with pytest.raises(N.NotationError) as error:
        N.parse(text)
    return [(i.code, i.line) for i in error.value.issues]


def codes(text, changing=False):
    tree = N.parse(text)
    return [(i.code, i.line) for i in N.analyze(tree, changing)]


def test_parse_extended():
    tree = N.parse(diagram('extended.hsm'))
    assert N.analyze(tree) == []
    job = vertex(tree, 'Job')
    assert (job.kind, job.reference) == (N.SUBMACHINE, 'Worker')
    assert [(c.kind, c.name) for c in job.children] == [
        (N.ENTRY_POINT, 'Start'), (N.EXIT_POINT, 'Done'),
        (N.EXIT_POINT, 'Failed')]
    assert vertex(tree, 'Job::Done').transitions[0].target is \
        vertex(tree, 'Ready')
    assert vertex(tree, 'Ready').transitions[0].target is \
        vertex(tree, 'Job::Start')
    history = vertex(tree, 'Oven::H')
    assert (history.kind, history.transitions[0].target.path) == \
        (N.HISTORY, 'Oven::Heating')
    resume = vertex(tree, 'Oven::Resume').transitions[0]
    assert (resume.action, resume.target.path) == ('resume()', 'Oven::Heating')
    tick = vertex(tree, 'Oven::Heating').internals[0]
    assert (tick.event, tick.guard, tick.propagation, tick.action) == \
        ('TICK', 't > 0', N.PROPAGATE, 't -= 1')
    door = vertex(tree, 'Oven').transitions[0]
    assert (door.propagation, door.target.path) == (N.BLOCK, 'Oven::H')
    pause = vertex(tree, 'Ready').internals[0]
    assert (pause.event, pause.propagation, pause.action) == \
        ('PAUSE', N.DEFER, '')
    assert vertex(tree, 'Busy::Deep', 1).kind == N.DEEP_HISTORY


def test_flag_without_guard_and_was():
    tree = N.parse('machine M\n  initial -> A\n  state A (was Old)\n'
                   '    E propagate -> A / x()\n    F block /\n'
                   '  submachine S (was T) of M2\n')
    a = vertex(tree, 'A')
    assert a.was == 'Old'
    assert (a.transitions[0].event, a.transitions[0].propagation) == \
        ('E', N.PROPAGATE)
    assert (a.internals[0].event, a.internals[0].propagation) == \
        ('F', N.BLOCK)
    assert (vertex(tree, 'S').was, vertex(tree, 'S').reference) == ('T', 'M2')


@pytest.mark.parametrize('text, expected', [
    ('machine M\n  state A\n    [x] propagate -> A\n', [('N30', 3)]),
    ('machine M\n  state A\n    E -> A / defer\n', [('N31', 3)]),
    ('machine M\n  submachine S\n', [('N32', 2)]),
    ('machine M\n  submachine S of\n', [('N32', 2)]),
    ('machine M\n  submachine S of N\n    state X\n', [('N33', 3)]),
    ('machine M\n  submachine S of N\n    entry/ x()\n', [('N33', 3)]),
    ('machine M\n  submachine S of N\n    E / x()\n', [('N33', 3)]),
    ('machine M\n  state A\n    history H E -> A\n', [('N34', 3)]),
    ('machine M\n  state A\n    entry point P E\n', [('N34', 3)]),
    ('machine M\n  state A\n    history\n', [('N07', 3)]),
    ('machine M\n  state A (was)\n', [('N06', 2)]),
])
def test_extended_syntax_issues(text, expected):
    assert issues(text) == expected


@pytest.mark.parametrize('text, expected', [
    ('machine M\n  initial -> A\n  state A\n  history H\n',
     [('S12', 4)]),
    ('machine M\n  initial -> A\n  state A\n    history H\n'
     '    history G\n    initial -> X\n    state X\n', [('S13', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> S\n'
     '  submachine S of Nowhere\n', [('S14', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> S\n'
     '  submachine S of M\n', [('S15', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> S::In\n'
     '  submachine S of N\n    entry point In\nmachine N\n'
     '  initial -> B\n  state B\n', [('S16', 6)]),
    ('machine M\n  initial -> A\n  state A\n    E -> S::In\n'
     '  submachine S of N\n    entry point In -> A\nmachine N\n'
     '  initial -> B\n  entry point In -> B\n  state B\n', [('S17', 6)]),
    ('machine M\n  initial -> A\n  state A\n    E -> Out\n'
     '  exit point Out -> A\n', [('S18', 5)]),
])
def test_extended_semantic_issues(text, expected):
    assert codes(text) == expected


def test_point_transition_on_an_event():
    tree = N.parse('machine M\n  initial -> S::In\n  submachine S of N\n'
                   '    entry point In\n    exit point Out DONE [ok] -> A\n'
                   '  state A\nmachine N\n  initial -> B\n'
                   '  entry point In -> B\n  state B\n    E -> Out\n'
                   '  exit point Out\n')
    assert N.analyze(tree) == []
    out = vertex(tree, 'S::Out').transitions[0]
    assert (out.event, out.guard, out.target.path) == ('DONE', 'ok', 'A')
    assert '    exit point Out DONE [ok] -> A\n' in N.render(tree)


def test_new_diagram_refuses_the_change_forms():
    text = 'machine M\n  initial -> A\n  state A (was B)\n  final _f1\n' \
        '    \n'
    assert codes(text) == [('U01', 3), ('U02', 4)]
    assert [c for c in codes(text, changing=True) if c[0][0] == 'U'] == []


def test_reached_through_points_and_submachines():
    assert codes('machine M\n  initial -> A\n  state A\n    E -> S::In\n'
                 '  submachine S of N\n    entry point In\n'
                 '    exit point Out -> B\n  state B\nmachine N\n'
                 '  initial -> C\n  entry point In -> C\n  state C\n'
                 '    E -> Out\n  exit point Out\n') == []


def test_good_file():
    tree = N.parse(diagram('extended.hsm'))
    N.analyze(tree)
    text = B.encode(B.build(tree, B.GEOMETRY_NONE))
    path = os.path.join(GOOD, 'extended.graphml')
    if REGEN:
        with open(path, 'w', encoding='utf-8') as good:
            good.write(text)
    with open(path, encoding='utf-8') as good:
        assert text == good.read()
    B.verify(text)


def test_built_with_geometry(tmp_path):
    tree = N.parse(diagram('extended.hsm'))
    N.analyze(tree)
    document = B.build(tree)
    assert document.check_geometry()
    caller = document.get_state_machines()[0]
    job = [e for e in caller.get_children()
           if e.get_type() == CyberiadaML.elementSubmachineState][0]
    worker = document.get_state_machines()[1]
    assert job.get_submachine_reference() == worker.get_id()
    text = B.encode(document)
    B.verify(text)
    path = tmp_path / 'extended.graphml'
    path.write_text(text, encoding='utf-8')
    findings = validate(str(path))
    if findings is None:
        pytest.skip('cyberiadaml-compat-tests is not found')
    assert findings == []


@pytest.mark.parametrize('name', ['lift.hsm', 'elements.hsm', 'extended.hsm'])
def test_render_round_trip(name):
    tree = N.parse(diagram(name))
    N.analyze(tree)
    text = N.render(tree)
    again = N.parse(text)
    assert N.analyze(again) == []
    assert N.render(again) == text


def test_render_forms():
    tree = N.parse('name: Doc\ndescription: line one\n    line two\n'
                   'machine M\n  initial -> "Doors open" / a()\n'
                   '    b()\n  state "Doors open"\n    entry/ x()\n'
                   '        y()\n    E /\n  state A\n    state Doors\n'
                   '    initial -> Doors\n  state B\n    state Doors\n'
                   '    initial -> Doors\n    E -> A::Doors\n')
    N.analyze(tree)
    tree.notes.append((None, 'platform: ArduinoUno'))
    tree.notes.append((tree.machines[0], 'comment: the lift'))
    text = N.render(tree)
    assert text.startswith('name: Doc\ndescription: line one\n    line two\n'
                           '# note: platform: ArduinoUno\nmachine M\n'
                           '  # note: comment: the lift\n'
                           '  initial -> "Doors open" / a()\n      b()\n')
    assert '    entry/ x()\n        y()\n    E /\n' in text
    assert '    E -> A::Doors\n' in text
    assert N.parse(text).description == 'line one\nline two'
