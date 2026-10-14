# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the notation parser
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

import pytest

from conftest import diagram
from hsm_maker import notation as N


def issues(text):
    with pytest.raises(N.NotationError) as error:
        N.parse(text)
    return [(i.code, i.line) for i in error.value.issues]


def vertex(diagram_, path):
    return [v for v in diagram_.walk() if v.path == path][0]


def test_lift():
    lift = N.parse(diagram('lift.hsm'))
    assert lift.name == 'Lift'
    assert lift.description == 'A lift with one call button on every floor'
    assert [m.name for m in lift.machines] == ['Lift']
    assert [(v.kind, v.path) for v in lift.walk()] == [
        ('machine', ''), ('initial', ''), ('state', 'Idle'),
        ('state', 'Moving'), ('state', 'Moving::MovingUp'),
        ('state', 'Moving::MovingDown'), ('state', 'DoorsOpen')]
    idle = vertex(lift, 'Idle')
    assert [(b.kind, b.action) for b in idle.behaviours] == \
        [('entry', 'lamp_off()')]
    assert [(t.event, t.guard, t.target_ref, t.action, t.line)
            for t in idle.transitions] == [
        ('CALL', 'call_floor > floor', 'MovingUp', 'target = call_floor', 8),
        ('CALL', 'call_floor < floor', 'MovingDown', 'target = call_floor', 10),
        ('CALL', 'call_floor == floor', 'DoorsOpen', '', 12)]
    up = vertex(lift, 'Moving::MovingUp')
    assert [(t.event, t.guard, t.action, t.target_ref)
            for t in up.internals] == \
        [('FLOOR', 'floor != target', 'floor += 1', None)]
    initial = lift.machines[0].children[0]
    assert (initial.kind, initial.transitions[0].action) == \
        ('initial', 'floor = 1')
    assert up.machine is lift.machines[0]


def test_elements():
    tree = N.parse(diagram('elements.hsm'))
    assert [m.name for m in tree.machines] == ['Bomb', 'Second machine']
    timing = vertex(tree, 'Timing')
    assert timing.internals[0].action == 'code = code * 10 + d\nshow(code)'
    assert timing.internals[0].event == 'DIGIT(d)'
    check = vertex(tree, 'Check')
    assert [(t.guard, t.target_ref) for t in check.transitions] == \
        [('timeout == 0', 'Boom'), ('else', 'Timing')]
    assert vertex(tree, 'Quoted state').transitions[0].target_ref == 'Outer'
    inner = vertex(tree, 'Outer::Inner')
    assert [(t.event, t.guard, t.target_ref) for t in inner.transitions] == \
        [('', 'done', '"Quoted state"')]
    assert vertex(tree, 'Halt').kind == N.TERMINATE


def test_lexical():
    text = ('\ufeffmachine M\r\n'
            '\r\n'
            '  # a comment\r\n'
            '  initial -> A\r\n'
            '  state A   \r\n'
            '    E /\r\n'
            '      if x:\r\n'
            '        # dropped\r\n'
            '          y()\r\n'
            '    F\r\n'
            '      [a / b]\r\n'
            '      -> A\r\n')
    tree = N.parse(text)
    state = vertex(tree, 'A')
    assert state.internals[0].action == 'if x:\n    y()'
    assert (state.transitions[0].event, state.transitions[0].guard,
            state.transitions[0].line) == ('F', 'a / b', 10)


def test_indentation_free_width():
    tree = N.parse('machine M\n    initial -> A\n    state A\n'
                   '         state B\n      state C\n')
    assert [v.path for v in tree.walk()] == ['', '', 'A', 'A::B', 'A::C']


def test_fence():
    answer = 'Here it is:\n```hsm\nmachine M\n  initial -> A\n  state A\n' \
             '```\nDone.'
    assert N.extract(answer) == 'machine M\n  initial -> A\n  state A\n'
    assert N.extract('machine M') == 'machine M'
    assert N.extract('```\nmachine M\n') == 'machine M\n'


@pytest.mark.parametrize('event', [
    'CALL(floor)', 'button.PRESSED', 'Сенсор.ЦельПолучена', 'TWO WORDS',
    'E_1'])
def test_good_events(event):
    tree = N.parse('machine M\n  initial -> A\n  state A\n'
                   '    {} -> A\n'.format(event))
    assert vertex(tree, 'A').transitions[0].event == event


@pytest.mark.parametrize('text, expected', [
    ('machine M\n  initial -> A\n  state A\n\tstate B\n', [('N01', 4)]),
    ('state A\n', [('N02', 1)]),
    ('machine M\n  machine N\n', [('N03', 2)]),
    ('# nothing\n', [('N04', None)]),
    ('machine M\n  state Doors Open\n', [('N06', 2)]),
    ('machine M\n  state\n', [('N07', 2)]),
    ('machine M\n  final\n', [('N07', 2)]),
    ('machine M\n  state "Open\n', [('N08', 2)]),
    ('machine M\n  state A::B\n', [('N09', 2)]),
    ('machine M\n  initial -> A\n  E -> A\n', [('N10', 3)]),
    ('machine M\n  entry/ x()\n', [('N11', 2)]),
    ('machine M\n  choice C\n    E [x] -> A\n', [('N12', 3)]),
    ('machine M\n  choice C\n    state S\n', [('N12', 3)]),
    ('machine M\n  state A\n    E-1 -> A\n', [('N13', 3)]),
    ('machine M\n  state A\n    CALL(a, b) -> A\n', [('N13', 3)]),
    ('machine M\n  state A\n    E defer -> A\n', [('N14', 3)]),
    ('machine M\n  state A\n    exit -> A\n', [('N14', 3)]),
    ('machine M\n  state A\n    E [x > 0 -> A\n', [('N15', 3)]),
    ('machine M\n  state A\n    E [a[0] > 1] -> A\n', [('N16', 3)]),
    ('machine M\n  state A\n    E [ ] -> A\n', [('N17', 3)]),
    ('machine M\n  state A\n    E -> / x()\n', [('N18', 3)]),
    ('machine M\n  state A\n    E [x]\n', [('N19', 3)]),
    ('machine M\n  state A\n    E -> A [x]\n', [('N20', 3)]),
    ('machine M\n  state A\n    entry/\n', [('N21', 3)]),
    ('machine M\n  state A\n    do/ x()\n', [('N22', 3)]),
    ('machine M\n  state A\n    E / defer x()\n', [('N23', 3)]),
    ('machine M\n  initial E -> A\n', [('N24', 2)]),
    ('machine M\n  initial\n', [('N24', 2)]),
    ('machine M\n  choice C\n    -> A\n', [('N25', 3)]),
    ('machine M\n  final F\n    E -> A\n', [('N26', 2)]),
    ('name: A\nname: B\nmachine M\n', [('N27', 2)]),
    ('machine M\nname: B\n', [('N27', 2)]),
    ('description:\nmachine M\n', [('N28', 1)]),
    ('machine M\n  state A\n    [x] / y()\n', [('N29', 3)]),
])
def test_syntax_issues(text, expected):
    assert issues(text) == expected


def test_all_issues_reported():
    assert issues('machine M\n  state A\n    E-1 -> A\n    do/ x\n'
                  '  E -> A\n') == [('N13', 3), ('N22', 4), ('N10', 5)]


def test_entry_with_space_and_escaped_guard():
    tree = N.parse('machine M\n  initial -> A\n  state A\n'
                   '    entry / go()\n    E [a\\[0\\] > 1] -> A\n')
    state = vertex(tree, 'A')
    assert state.behaviours[0].action == 'go()'
    assert state.transitions[0].guard == 'a\\[0\\] > 1'
