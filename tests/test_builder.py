# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the builder
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


def tree(text):
    result = N.parse(text)
    assert N.analyze(result) == []
    return result


def elements(document):
    found = {}

    def walk(element):
        found[element.get_qualified_name()] = element
        for child in (element.get_children() if element.has_children()
                      else []):
            walk(child)
    for machine in document.get_state_machines():
        for child in machine.get_children():
            walk(child)
    return found


@pytest.mark.parametrize('name', ['lift', 'elements'])
def test_good_files(name):
    text = B.encode(B.build(tree(diagram(name + '.hsm')), B.GEOMETRY_NONE))
    path = os.path.join(GOOD, name + '.graphml')
    if REGEN:
        with open(path, 'w', encoding='utf-8') as good:
            good.write(text)
    with open(path, encoding='utf-8') as good:
        assert text == good.read()
    B.verify(text)


@pytest.mark.parametrize('name', ['lift', 'elements'])
def test_geometry(name, tmp_path):
    document = B.build(tree(diagram(name + '.hsm')))
    assert document.meta().get_geometry() == \
        CyberiadaML.geometryDeclarationFull
    for element in elements(document).values():
        assert element.has_geometry()
    text = B.encode(document)
    B.verify(text)
    path = tmp_path / (name + '.graphml')
    path.write_text(text, encoding='utf-8')
    findings = validate(str(path))
    if findings is None:
        pytest.skip('cyberiadaml-compat-tests is not found')
    assert findings == []


@pytest.mark.parametrize('name', [
    'lift',
    pytest.param('elements', marks=pytest.mark.xfail(
        reason='libhtreegeom: long transition labels overflow the machine '
        'border'))])
def test_layout_fits_the_border(name):
    assert B.build(tree(diagram(name + '.hsm'))).check_geometry()


def test_no_geometry_declared():
    document = B.build(tree(diagram('lift.hsm')), B.GEOMETRY_NONE)
    assert document.meta().get_geometry() == \
        CyberiadaML.geometryDeclarationNone
    assert 'geometry/ none' in B.encode(document)


def test_elements_and_names():
    document = B.build(tree(diagram('elements.hsm')), B.GEOMETRY_NONE)
    assert document.get_name() == 'Elements'
    assert document.meta().get_string('description') == \
        'The elements of the notation'
    machines = document.get_state_machines()
    assert [m.get_name() for m in machines] == ['Bomb', 'Second machine']
    found = elements(document)
    # the two-string overloads name the pseudostates, not identify them
    assert found['Check'].get_name() == 'Check'
    assert found['Boom'].get_name() == 'Boom'
    assert found['Halt'].get_name() == 'Halt'
    assert found['Outer::Inner'].get_name() == 'Inner'
    paths = [v.path for v in tree(diagram('elements.hsm')).walk()
             if v.kind in N.NAMED]
    assert set(paths) <= set(found)


def test_actions_and_transitions():
    document = B.build(tree(diagram('lift.hsm')), B.GEOMETRY_NONE)
    found = elements(document)
    actions = [(a.get_trigger(), a.get_guard(), a.get_behavior())
               for a in found['Moving::MovingUp'].get_actions()]
    assert ('', '', 'motor_up()') in actions
    assert ('FLOOR', 'floor != target', 'floor += 1') in actions
    machine = document.get_state_machines()[0]
    transitions = [(t.get_source_element_id(), t.get_target_element_id())
                   for t in machine.get_transitions()]
    assert len(transitions) == 6
    assert (found['Idle'].get_id(), found['Moving::MovingUp'].get_id()) in \
        transitions


def test_not_analysed():
    with pytest.raises(ValueError):
        B.build(N.parse(diagram('lift.hsm')))


def test_library_error_has_the_line():
    def reject():
        raise CyberiadaML.ParametersException('rejected')
    with pytest.raises(B.BuildError) as error:
        B._call(7, reject)  # pylint: disable=protected-access
    issue = error.value.issues[0]
    assert (issue.code, issue.line, issue.fields['message']) == \
        ('B01', 7, 'rejected')


def test_verify_reports_the_reason():
    text = B.encode(B.build(tree('machine M\n  initial -> A\n  state A\n'
                                 '    E -> A\n'), B.GEOMETRY_NONE))
    with pytest.raises(B.BuildError) as error:
        B.verify(text.replace('>E/<', '>E-1/<'))
    issue = error.value.issues[0]
    assert issue.code == 'B02'
    assert 'regexp' in issue.fields['message']


def test_cyrillic_names_and_events():
    text = B.encode(B.build(tree(
        'machine Тостер\n  initial -> Нагрев\n  state Нагрев\n'
        '    ДВЕРЦА_ОТКРЫТА -> Открыта / lamp_on()\n  state Открыта\n'
        '    Дверца.ЗАКРЫТА -> Нагрев\n')))
    B.verify(text)
    assert 'ДВЕРЦА_ОТКРЫТА' in text
