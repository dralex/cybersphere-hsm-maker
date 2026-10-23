# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The reader: a CyberiadaML document to the notation tree
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

"""A diagram to be changed: the document read into the notation tree with
the element ids, the comments, names for the unnamed elements and notes for
what the notation cannot show."""

from .cyberiadaml import CyberiadaML

from .builder import BINDING_ERRORS, PLATFORM_LANGUAGE
from .notation import (Behaviour, Comment, Diagram, NotationError, Subject,
                       Transition, Vertex, MACHINE, STATE, INITIAL, FINAL,
                       TERMINATE, CHOICE, HISTORY, DEEP_HISTORY, ENTRY_POINT,
                       EXIT_POINT, SUBMACHINE, COMMENT, TAILED, PROPAGATE,
                       BLOCK, DEFER, UNNAMED, PATH, SUBJECT_ELEMENT,
                       SUBJECT_NAME, SUBJECT_BODY, parse, render)

KINDS = {
    CyberiadaML.elementSimpleState: STATE,
    CyberiadaML.elementCompositeState: STATE,
    CyberiadaML.elementSubmachineState: SUBMACHINE,
    CyberiadaML.elementInitial: INITIAL,
    CyberiadaML.elementFinal: FINAL,
    CyberiadaML.elementChoice: CHOICE,
    CyberiadaML.elementTerminate: TERMINATE,
    CyberiadaML.elementShallowHistory: HISTORY,
    CyberiadaML.elementDeepHistory: DEEP_HISTORY,
    CyberiadaML.elementEntryPoint: ENTRY_POINT,
    CyberiadaML.elementExitPoint: EXIT_POINT,
}
COMMENTS = (CyberiadaML.elementComment, CyberiadaML.elementFormalComment)
PROPAGATIONS = {
    CyberiadaML.eventPropagationNone: '',
    CyberiadaML.eventPropagationPropagate: PROPAGATE,
    CyberiadaML.eventPropagationBlock: BLOCK,
    CyberiadaML.eventPropagationDefer: DEFER,
}
# the prefixes of the names given to the unnamed elements: _final1 ...
SYNTHETIC = {MACHINE: 'machine', STATE: 'state', FINAL: 'final',
             CHOICE: 'choice', TERMINATE: 'terminate', HISTORY: 'history',
             DEEP_HISTORY: 'deep', ENTRY_POINT: 'entry', EXIT_POINT: 'exit',
             SUBMACHINE: 'submachine', COMMENT: 'comment'}
SUBJECT_KINDS = {CyberiadaML.commentSubjectElement: SUBJECT_ELEMENT,
                 CyberiadaML.commentSubjectName: SUBJECT_NAME,
                 CyberiadaML.commentSubjectData: SUBJECT_BODY}
META_NAME = 'CGML_META'
META_NOTES = ('platform', 'platformVersion', 'target', 'markupLanguage',
              'author', 'version')
NOTE_LIMIT = 100


class ReadError(Exception):
    """The diagram cannot be read or shown in the notation."""


def decode(graphml):
    """The CyberiadaML document of a text. The library's skipping of the
    empty actions also drops `E / defer`, so the reader drops only the
    empty entry and exit behaviours itself."""
    document = CyberiadaML.Document()
    try:
        document.decode(graphml)
    except BINDING_ERRORS as error:
        raise ReadError('the library cannot read the diagram: {}'.format(
            error)) from error
    return document


def _short(text):
    text = ' '.join(text.split())
    return text if len(text) <= NOTE_LIMIT else text[:NOTE_LIMIT - 3] + '...'


def _note(comment):
    """The note of a comment: its kind or formal name, its text, its
    subjects."""
    body = _short(comment.get_body())
    if comment.is_human_readable():
        text = 'comment: ' + body
    else:
        text = '{}: {}'.format(comment.get_name() or 'formal comment', body)
    names = []
    for subject in comment.get_subjects():
        element = subject.get_element()
        if element is not None:
            names.append(element.get_name() or element.get_id())
    if names:
        text += ' (on {})'.format(', '.join(names))
    return text


def _writable(title):
    """Whether the notation can write a comment title as its name."""
    return bool(title) and title == title.strip() and '"' not in title and \
        '\n' not in title and PATH not in title and \
        not title.startswith(UNNAMED)


def _hidden(target, subject):
    """The links the notation cannot write: to an initial or its
    transition, a name fragment of a transition, an empty fragment."""
    if isinstance(target, Vertex) and target.kind == INITIAL:
        return True
    if isinstance(target, Transition) and \
       (target.source.kind == INITIAL or subject.kind == SUBJECT_NAME):
        return True
    return subject.kind != SUBJECT_ELEMENT and not subject.fragment


class _Reader:
    def __init__(self, document):
        self.document = document
        self.diagram = Diagram()
        self.vertices = {}
        self.edges = {}
        self.comments = {}
        self.taken = set()

    def name(self, kind, given):
        """The name of an element, a fresh `_kindN` name when it has none."""
        if given:
            self.taken.add(given)
            return given, False
        number = 1
        while UNNAMED + SYNTHETIC[kind] + str(number) in self.taken:
            number += 1
        name = UNNAMED + SYNTHETIC[kind] + str(number)
        self.taken.add(name)
        return name, True

    def actions(self, element, vertex):
        for action in element.get_actions():
            kind = action.get_type()
            if kind != CyberiadaML.actionTransition and \
               not action.get_behavior().strip():
                continue
            if kind == CyberiadaML.actionEntry:
                vertex.behaviours.append(Behaviour('entry',
                                                   action.get_behavior(), 0))
            elif kind == CyberiadaML.actionExit:
                vertex.behaviours.append(Behaviour('exit',
                                                   action.get_behavior(), 0))
            else:
                vertex.internals.append(Transition(
                    0, vertex, action.get_trigger(), action.get_guard(),
                    action.get_behavior(), None,
                    PROPAGATIONS.get(action.get_propagation(), '')))

    def children(self, collection, parent):
        for element in collection.get_children():
            kind = element.get_type()
            if kind == CyberiadaML.elementTransition:
                continue
            if kind in COMMENTS:
                if element.get_name() == META_NAME:
                    continue
                if element.is_human_readable():
                    self.comment(element, collection, parent)
                else:
                    self.diagram.notes.append((parent, _note(element)))
                continue
            if kind not in KINDS:
                raise ReadError('the notation cannot show the element {}'
                                .format(element.get_id()))
            kind = KINDS[kind]
            if kind == INITIAL:
                name, unnamed = None, False
            else:
                name, unnamed = self.name(kind, element.get_name())
            vertex = Vertex(kind, name, 0, parent)
            vertex.element_id = element.get_id()
            vertex.unnamed = unnamed
            self.vertices[vertex.element_id] = vertex
            if kind == STATE:
                self.actions(element, vertex)
            if kind == SUBMACHINE:
                vertex.reference = element.get_submachine_reference()
            if kind in (STATE, SUBMACHINE) and element.has_children():
                self.children(element, vertex)

    def comment(self, element, collection, parent):
        """An informal comment; a submachine holds none in the notation, its
        level shows it."""
        holder = parent.parent if parent.kind == SUBMACHINE else parent
        comment = Comment(None, 0, holder)
        comment.element_id = element.get_id()
        comment.title = element.get_name() or None
        comment.body = (element.get_body() or '').replace('\r\n', '\n') \
            .replace('\r', '\n')
        comment.parent_element_id = collection.get_id()
        self.comments[comment.element_id] = (comment, element)

    def subjects(self):
        """The links of the comments to the vertices, the transitions and
        the comments of the tree."""
        for comment, element in self.comments.values():
            for link in element.get_subjects():
                linked = link.get_element()
                if linked is None:
                    continue
                key = linked.get_id()
                target = self.vertices.get(key) or self.edges.get(key)
                if target is None and key in self.comments:
                    target = self.comments[key][0]
                subject = Subject(SUBJECT_KINDS.get(link.get_type(),
                                                    SUBJECT_ELEMENT),
                                  link.get_fragment() or '')
                if target is None or _hidden(target, subject):
                    continue
                subject.target = target
                subject.element_id = key
                comment.subjects.append(subject)

    def comment_names(self, machine):
        """A title the notation can write and unique in the machine is the
        name of its comment, else the comment gets a `_commentN` name."""
        comments = [c for v in machine.walk() for c in v.comments]
        titles = [c.title for c in comments]
        for comment in comments:
            if _writable(comment.title) and titles.count(comment.title) == 1:
                comment.name = comment.title
                self.taken.add(comment.title)
        for comment in comments:
            if comment.name is None:
                comment.name, comment.unnamed = self.name(COMMENT, None)

    def transitions(self, machine):
        for element in machine.get_transitions():
            source = self.vertices.get(element.get_source_element_id())
            target = self.vertices.get(element.get_target_element_id())
            if source is None or target is None:
                raise ReadError('the notation cannot show the transition {}'
                                .format(element.get_id()))
            if element.has_action():
                action = element.get_action()
                transition = Transition(
                    0, source, action.get_trigger(), action.get_guard(),
                    action.get_behavior(), None,
                    PROPAGATIONS.get(action.get_propagation(), ''))
            else:
                transition = Transition(0, source)
            transition.target = target
            transition.element_id = element.get_id()
            source.transitions.append(transition)
            self.edges[transition.element_id] = transition

    def read(self):
        diagram = self.diagram
        meta = self.document.meta()
        diagram.name = self.document.get_name() or None
        diagram.description = meta.get_string('description') or None
        diagram.language = meta.get_string(PLATFORM_LANGUAGE) or None
        for key in META_NOTES:
            if meta.get_string(key):
                diagram.notes.append((None, '{}: {}'.format(
                    key, _short(meta.get_string(key)))))
        machines = self.document.get_state_machines()
        by_id = {}
        for machine in machines:
            name, unnamed = self.name(MACHINE, machine.get_name())
            vertex = Vertex(MACHINE, name, 0)
            vertex.element_id = machine.get_id()
            vertex.unnamed = unnamed
            diagram.machines.append(vertex)
            by_id[vertex.element_id] = vertex
        for machine, vertex in zip(machines, diagram.machines):
            self.children(machine, vertex)
        for machine in machines:
            self.transitions(machine)
        self.subjects()
        for vertex in diagram.machines:
            self.comment_names(vertex)
        for vertex in diagram.walk():
            if vertex.kind == SUBMACHINE:
                if vertex.reference not in by_id:
                    raise ReadError('the submachine {} refers outside the '
                                    'document'.format(vertex.element_id))
                vertex.reference = by_id[vertex.reference].name
            if vertex.kind == INITIAL and len(vertex.transitions) != 1:
                raise ReadError('the initial {} needs one transition'
                                .format(vertex.element_id))
            if vertex.kind in TAILED and len(vertex.transitions) > 1:
                raise ReadError('the {} {} has more than one transition'
                                .format(vertex.kind, vertex.element_id))
        return diagram


def read(document):
    """The notation tree of a document with the element ids; raise
    ReadError for what the notation cannot show."""
    diagram = _Reader(document).read()
    try:
        parse(render(diagram))
    except NotationError as error:
        issue = error.issues[0]
        raise ReadError('the notation cannot show the diagram: line {}: {} '
                        '{}'.format(issue.line, issue.code,
                                    issue.fields)) from error
    return diagram
