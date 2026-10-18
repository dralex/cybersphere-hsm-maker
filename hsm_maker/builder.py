# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The builder: the notation tree to a CyberiadaML document
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

"""The analysed notation tree to a CyberiadaML document through the binding
of libcyberiadamlpp-py; the layout, the encoding and the strict check."""

import os
import sys
import tempfile

from .cyberiadaml import CyberiadaML

from .notation import (Issue, STATE, INITIAL, FINAL, TERMINATE, CHOICE,
                       HISTORY, DEEP_HISTORY, ENTRY_POINT, EXIT_POINT,
                       SUBMACHINE, PROPAGATE, BLOCK, DEFER)

GEOMETRY_FULL = 'full'
GEOMETRY_NONE = 'none'
GEOMETRY_UPDATE = 'update'
GEOMETRIES = (GEOMETRY_FULL, GEOMETRY_NONE)
CHANGE_GEOMETRIES = (GEOMETRY_UPDATE, GEOMETRY_FULL, GEOMETRY_NONE)
# the meta key of the code language
PLATFORM_LANGUAGE = 'platformLanguage'

# the classes are registered apart and share no base but Exception
BINDING_ERRORS = tuple(getattr(CyberiadaML, name) for name in (
    'Exception', 'FileException', 'FormatException', 'XMLException',
    'CybMLException', 'ActionException', 'MetainfoException',
    'ParametersException', 'NotFoundException', 'AssertException',
    'NotImplementedException') if hasattr(CyberiadaML, name))

PROPAGATION = {'': CyberiadaML.eventPropagationNone,
               PROPAGATE: CyberiadaML.eventPropagationPropagate,
               BLOCK: CyberiadaML.eventPropagationBlock,
               DEFER: CyberiadaML.eventPropagationDefer}

REASON_LINES = 3
STDERR = 2


class BuildError(Exception):
    """The library rejected the document."""

    def __init__(self, issues):
        super().__init__('; '.join(str(i.fields.get('message', i.code))
                                   for i in issues))
        self.issues = issues


def _call(line, method, *args):
    try:
        return method(*args)
    except BINDING_ERRORS as error:
        raise BuildError([Issue('B01', line, message=str(error))]) from error


def action_of(transition):
    """The CyberiadaML action of a transition of the tree."""
    if transition.event or transition.guard or transition.action or \
       transition.propagation:
        return CyberiadaML.Action(transition.event, transition.guard,
                                  transition.action,
                                  PROPAGATION[transition.propagation])
    return CyberiadaML.Action()


def actions_of(vertex):
    """The CyberiadaML actions of a state: the behaviours, then the
    internal transitions."""
    actions = []
    for behaviour in vertex.behaviours:
        kind = CyberiadaML.actionEntry if behaviour.kind == 'entry' \
            else CyberiadaML.actionExit
        actions.append(CyberiadaML.Action(kind, behaviour.action))
    actions.extend(action_of(t) for t in vertex.internals)
    return actions


def new_element(document, vertex, parent, machine_ids):
    """Create the element of a vertex in the parent element (positional
    arguments only: the two-string overloads read (id, name))."""
    line = vertex.line
    if vertex.kind == STATE:
        return _call(line, document.new_state, parent, vertex.name)
    if vertex.kind == INITIAL:
        return _call(line, document.new_initial, parent)
    if vertex.kind == FINAL:
        return _call(line, document.new_final, parent, vertex.name)
    if vertex.kind == TERMINATE:
        return _call(line, document.new_terminate, parent, vertex.name)
    if vertex.kind == CHOICE:
        return _call(line, document.new_choice, parent, vertex.name)
    if vertex.kind == HISTORY:
        return _call(line, document.new_shallow_history, parent, vertex.name)
    if vertex.kind == DEEP_HISTORY:
        return _call(line, document.new_deep_history, parent, vertex.name)
    if vertex.kind == ENTRY_POINT:
        return _call(line, document.new_entry, parent, vertex.name)
    if vertex.kind == EXIT_POINT:
        return _call(line, document.new_exit, parent, vertex.name)
    assert vertex.kind == SUBMACHINE
    return _call(line, document.new_submachine_state, parent,
                 machine_ids[vertex.reference], vertex.name)


def _vertex(document, vertex, parent, elements, machine_ids):
    element = new_element(document, vertex, parent, machine_ids)
    elements[id(vertex)] = element
    for action in actions_of(vertex):
        _call(vertex.line, element.add_action, action)
    for child in vertex.children:
        _vertex(document, child, element, elements, machine_ids)


def new_transition(document, machine, transition, source, target):
    """Create a transition of the tree between two elements."""
    if transition.target is None:
        raise ValueError('the diagram is not analysed')
    return _call(transition.line, document.new_transition, machine,
                 CyberiadaML.transitionExternal, source, target,
                 action_of(transition))


def _drawn(document):
    for machine in document.get_state_machines():
        if machine.has_geometry():
            return True
        for element in machine.find_elements_by_types([
                CyberiadaML.elementSimpleState,
                CyberiadaML.elementCompositeState,
                CyberiadaML.elementSubmachineState,
                CyberiadaML.elementInitial, CyberiadaML.elementFinal,
                CyberiadaML.elementChoice, CyberiadaML.elementTerminate]):
            if element.has_geometry():
                return True
    return False


def layout(document, geometry):
    """Lay the document out (full), complete its drawing (update; the full
    layout when nothing is drawn) or clean it (none); declare the
    geometry. The elements are recreated: fetch them again by id."""
    if geometry == GEOMETRY_NONE:
        if _drawn(document):
            _call(None, document.clean_geometry)
        document.meta().set_geometry(CyberiadaML.geometryDeclarationNone)
        return
    if geometry == GEOMETRY_UPDATE and _drawn(document):
        bordered = all(m.has_geometry() for m in document.get_state_machines())
        _call(None, document.update_geometry, bordered)
    else:
        _call(None, document.reconstruct_geometry, True)
    # without the declaration the edge geometry breaks the strict check
    document.meta().set_geometry(CyberiadaML.geometryDeclarationFull)


def build(diagram, geometry=GEOMETRY_FULL):
    """Create the document of an analysed diagram and lay it out. Raise
    BuildError."""
    document = CyberiadaML.Document()
    if diagram.name:
        _call(None, document.set_name, diagram.name)
    if diagram.description:
        _call(None, document.meta().set_string, 'description',
              diagram.description)
    if diagram.language:
        _call(None, document.meta().set_string, PLATFORM_LANGUAGE,
              diagram.language)
    elements = {}
    machine_ids = {}
    for machine in diagram.machines:
        element = _call(machine.line, document.new_state_machine,
                        machine.name)
        elements[id(machine)] = element
        machine_ids[machine.name] = element.get_id()
    for machine in diagram.machines:
        for child in machine.children:
            _vertex(document, child, elements[id(machine)], elements,
                    machine_ids)
    for machine in diagram.machines:
        for vertex in machine.walk():
            for transition in vertex.transitions:
                new_transition(document, elements[id(machine)], transition,
                               elements[id(vertex)],
                               elements.get(id(transition.target)))
    layout(document, geometry)
    return document


def encode(document):
    """The GraphML text of the document."""
    try:
        return document.encode(round=True)
    except BINDING_ERRORS as error:
        raise BuildError([Issue('B01', message=str(error))]) from error


def _captured(method, *args, **options):
    """Call the method with the C stderr in a file: the library prints the
    reason of a failure there, the exception carries only a source line."""
    sys.stderr.flush()
    with tempfile.TemporaryFile() as output:
        saved = os.dup(STDERR)
        os.dup2(output.fileno(), STDERR)
        failure = None
        try:
            method(*args, **options)
        except BINDING_ERRORS as error:
            failure = error
        finally:
            os.dup2(saved, STDERR)
            os.close(saved)
        output.seek(0)
        text = output.read().decode('utf-8', 'replace')
    return failure, text


def verify(graphml):
    """Read the text back with the strict check of the library."""
    failure, text = _captured(CyberiadaML.Document().decode, graphml,
                              strict=True)
    if failure is None:
        return
    reason = [line.strip() for line in text.splitlines() if line.strip()]
    message = '; '.join(reason[-REASON_LINES:]) if reason else str(failure)
    raise BuildError([Issue('B02', message=message)])
