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

import CyberiadaML

from .notation import Issue, STATE, INITIAL, FINAL, TERMINATE, CHOICE

GEOMETRY_FULL = 'full'
GEOMETRY_NONE = 'none'
GEOMETRIES = (GEOMETRY_FULL, GEOMETRY_NONE)

# the classes are registered apart and share no base but Exception
BINDING_ERRORS = tuple(getattr(CyberiadaML, name) for name in (
    'Exception', 'FileException', 'FormatException', 'XMLException',
    'CybMLException', 'ActionException', 'MetainfoException',
    'ParametersException', 'NotFoundException', 'AssertException',
    'NotImplementedException') if hasattr(CyberiadaML, name))

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


def _action(transition):
    if transition.event or transition.guard or transition.action:
        return CyberiadaML.Action(transition.event, transition.guard,
                                  transition.action)
    return CyberiadaML.Action()


def _vertex(document, vertex, parent, elements):
    # positional arguments only: the two-string overloads read (id, name)
    if vertex.kind == STATE:
        element = _call(vertex.line, document.new_state, parent, vertex.name)
    elif vertex.kind == INITIAL:
        element = _call(vertex.line, document.new_initial, parent)
    elif vertex.kind == FINAL:
        element = _call(vertex.line, document.new_final, parent, vertex.name)
    elif vertex.kind == TERMINATE:
        element = _call(vertex.line, document.new_terminate, parent,
                        vertex.name)
    else:
        assert vertex.kind == CHOICE
        element = _call(vertex.line, document.new_choice, parent, vertex.name)
    elements[id(vertex)] = element
    for behaviour in vertex.behaviours:
        kind = CyberiadaML.actionEntry if behaviour.kind == 'entry' \
            else CyberiadaML.actionExit
        _call(behaviour.line, element.add_action,
              CyberiadaML.Action(kind, behaviour.action))
    for transition in vertex.internals:
        _call(transition.line, element.add_action, _action(transition))
    for child in vertex.children:
        _vertex(document, child, element, elements)


def build(diagram, geometry=GEOMETRY_FULL):
    """Create the document of an analysed diagram; lay it out with
    GEOMETRY_FULL. Raise BuildError."""
    document = CyberiadaML.Document()
    if diagram.name:
        _call(None, document.set_name, diagram.name)
    if diagram.description:
        _call(None, document.meta().set_string, 'description',
              diagram.description)
    elements = {}
    for machine in diagram.machines:
        elements[id(machine)] = _call(machine.line,
                                      document.new_state_machine,
                                      machine.name)
        for child in machine.children:
            _vertex(document, child, elements[id(machine)], elements)
    for machine in diagram.machines:
        for vertex in machine.walk():
            for transition in vertex.transitions:
                if transition.target is None:
                    raise ValueError('the diagram is not analysed')
                _call(transition.line, document.new_transition,
                      elements[id(machine)], CyberiadaML.transitionExternal,
                      elements[id(vertex)], elements[id(transition.target)],
                      _action(transition))
    if geometry == GEOMETRY_FULL:
        _call(None, document.reconstruct_geometry, True)
        # without the declaration the edge geometry breaks the strict check
        document.meta().set_geometry(CyberiadaML.geometryDeclarationFull)
    else:
        document.meta().set_geometry(CyberiadaML.geometryDeclarationNone)
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
