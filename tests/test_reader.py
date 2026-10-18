# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the reader
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

from hsm_maker.cyberiadaml import CyberiadaML
from conftest import GOOD, diagram
from hsm_maker import builder as B
from hsm_maker import notation as N
from hsm_maker import reader as R

T = CyberiadaML.transitionExternal


def good(name):
    with open(os.path.join(GOOD, name + '.graphml'), encoding='utf-8') as source:
        return source.read()


@pytest.mark.parametrize('name', ['lift', 'elements', 'extended'])
def test_read_back(name):
    tree = R.read(R.decode(good(name)))
    source = N.parse(diagram(name + '.hsm'))
    N.analyze(source)
    assert N.render(tree) == N.render(source)


def test_element_ids():
    document = R.decode(good('lift'))
    tree = R.read(document)
    for vertex in tree.walk():
        element = document.find_element_by_id(vertex.element_id)
        assert element is not None
        if vertex.kind not in (N.MACHINE, N.INITIAL):
            assert element.get_name() == vertex.name
        for transition in vertex.transitions:
            assert document.find_element_by_id(transition.element_id) \
                is not None


def handmade():
    """A document with unnamed pseudostates, comments and meta."""
    d = CyberiadaML.Document()
    d.meta().set_string('platform', 'ArduinoUno')
    sm = d.new_state_machine('M')
    init = d.new_initial(sm)
    a = d.new_state(sm, 'A')
    a.add_action(CyberiadaML.Action(CyberiadaML.actionEntry, ''))
    a.add_action(CyberiadaML.Action('LATER', '', '',
                                    CyberiadaML.eventPropagationDefer))
    choice = d.new_choice(sm)
    final = d.new_final(sm)
    d.new_transition(sm, T, init, a, CyberiadaML.Action())
    d.new_transition(sm, T, a, choice, CyberiadaML.Action('GO'))
    d.new_transition(sm, T, choice, final, CyberiadaML.Action('', 'x'))
    d.new_transition(sm, T, choice, a, CyberiadaML.Action('', 'else'))
    comment = d.new_comment(sm, 'remember the timer')
    d.add_comment_to_element(comment, a)
    d.new_formal_comment(sm, 'CGML_COMPONENT timer', 'type/ Timer')
    return d


def test_unnamed_notes_and_actions():
    tree = R.read(R.decode(handmade().encode()))
    machine = tree.machines[0]
    names = [(v.kind, v.name, v.unnamed) for v in machine.children]
    assert (N.CHOICE, '_choice1', True) in names
    assert (N.FINAL, '_final1', True) in names
    a = [v for v in machine.children if v.name == 'A'][0]
    assert a.behaviours == []
    assert [(t.event, t.propagation) for t in a.internals] == \
        [('LATER', N.DEFER)]
    assert (None, 'platform: ArduinoUno') in tree.notes
    notes = [text for vertex, text in tree.notes if vertex is machine]
    assert notes == ['comment: remember the timer (on A)',
                     'CGML_COMPONENT timer: type/ Timer']
    text = N.render(tree)
    assert '# note: platform: ArduinoUno' in text
    assert 'choice _choice1\n    [x] -> _final1\n    [else] -> A\n' in text


def test_refused():
    d = CyberiadaML.Document()
    sm = d.new_state_machine('M')
    d.new_initial(sm)
    d.new_state(sm, 'A')
    with pytest.raises(R.ReadError):
        R.read(R.decode(d.encode()))
    with pytest.raises(R.ReadError):
        R.decode('<graphml>broken')


def test_built_documents_read_back():
    tree = N.parse(diagram('extended.hsm'))
    N.analyze(tree)
    document = B.build(tree)
    again = R.read(R.decode(B.encode(document)))
    assert N.render(again) == N.render(tree)
