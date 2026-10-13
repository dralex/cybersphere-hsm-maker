# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the name resolution and the semantic checks
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


def analyzed(text):
    tree = N.parse(text)
    return tree, N.analyze(tree)


def codes(text):
    return [(i.code, i.line) for i in analyzed(text)[1]]


def target(tree, path, index=0):
    source = [v for v in tree.walk() if v.path == path][0]
    found = source.transitions[index].target
    return found.path if found is not None else None


@pytest.mark.parametrize('name', ['lift.hsm', 'elements.hsm'])
def test_good_diagrams(name):
    tree, found = analyzed(diagram(name))
    assert found == []
    for vertex in tree.walk():
        for transition in vertex.transitions:
            assert transition.target is not None


def test_scoping():
    tree, found = analyzed(
        'machine M\n'
        '  initial -> A\n'
        '  state A\n'
        '    initial -> X\n'
        '    state X\n'
        '      GO -> Y\n'          # the own level first
        '      FAR -> Z\n'         # unique in the machine
        '      UP -> B\n'          # an enclosing level
        '    state Y\n'
        '      BACK -> A::X\n'     # a path
        '  state B\n'
        '    initial -> X\n'
        '    state X\n'
        '      GO -> Y\n'
        '    state Y\n'
        '      state Z\n'
        '      initial -> Z\n')
    assert found == []
    assert target(tree, 'A::X', 0) == 'A::Y'
    assert target(tree, 'A::X', 1) == 'B::Y::Z'
    assert target(tree, 'A::X', 2) == 'B'
    assert target(tree, 'A::Y') == 'A::X'
    assert target(tree, 'B::X') == 'B::Y'


def test_ambiguous_and_unknown():
    tree, found = analyzed(
        'machine M\n  initial -> A\n  state A\n    initial -> X\n'
        '    state X\n  state B\n    initial -> X\n    state X\n'
        '  state C\n    GO -> X\n    GO -> Bb\n')
    assert [(i.code, i.line) for i in found] == [('R02', 10), ('R01', 11)]
    assert found[0].fields['candidates'] == 'A::X, B::X'
    assert found[1].fields['known'].split(', ')[0] == 'B'
    assert target(tree, 'C') is None


@pytest.mark.parametrize('text, expected', [
    ('machine M\n  initial -> A\n  state A\n    E -> terminate\n',
     [('R03', 4)]),
    ('machine M\n  initial -> A\n  state A\n    E -> M\n', [('R04', 4)]),
    ('machine M\n  initial -> A\n  state A\nmachine M\n  initial -> B\n'
     '  state B\n', [('S01', 4)]),
    ('machine M\n  initial -> A\n  state A\n  state A\n', [('S02', 4)]),
    ('machine M\n  initial -> A\n  initial -> A\n  state A\n', [('S03', 3)]),
    ('machine M\n  state A\n', [('S04', 1)]),
    ('machine M\n', [('S05', 1)]),
    ('machine M\n  initial -> A\n  state A\n    entry/ a()\n'
     '    entry/ b()\n', [('S06', 5)]),
    ('machine M\n  initial -> A\n  state A\n    initial -> B\n'
     '  state B\n', [('S07', 4)]),
    ('machine M\n  initial -> A\n  state A\n    initial -> A\n',
     [('S07', 4)]),
    ('machine M\n  initial -> A\n  state A\n    E -> B\n  state B\n'
     '    state C\n', [('S08', 4)]),
    ('machine M\n  initial -> A\n  state A\n    E -> C\n  choice C\n'
     '    [x] -> A\n', [('S09', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> C\n    F -> C\n'
     '  choice C\n    [x] -> A\n    [else] -> A\n', [('S10', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> C\n  choice C\n'
     '    [else] -> A\n    [else] -> A\n', [('S11', 7)]),
])
def test_semantic_issues(text, expected):
    assert codes(text) == expected


def test_local_transition_into_parent():
    assert codes('machine M\n  initial -> A\n  state A\n    state B\n'
                 '      E -> A\n    initial -> B\n') == []
    assert codes('machine M\n  initial -> A\n  state A\n    state B\n'
                 '      E -> A\n') == [('S08', 2)]


def test_unreachable_is_a_warning():
    found = analyzed('machine M\n  initial -> A\n  state A\n  state B\n'
                     '  state C\n    E -> A\n')[1]
    assert [(i.code, i.line, i.severity) for i in found] == [
        ('W01', 4, N.WARNING), ('W01', 5, N.WARNING)]


def test_reached_through_parent_and_choice():
    assert codes('machine M\n  initial -> P\n  state P\n    initial -> A\n'
                 '    state A\n    E -> C\n  choice C\n    [x] -> F\n'
                 '    [else] -> P\n  final F\n') == []
