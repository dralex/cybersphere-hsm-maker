# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The patcher: a changed notation applied to the document it was read from
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

"""The difference of the tree read from a document and the changed tree,
applied to the document itself: what stays keeps its id, its geometry and
what the notation does not show (docs/ARCHITECTURE.md, The update)."""

import textwrap

from .cyberiadaml import CyberiadaML

from .builder import (BINDING_ERRORS, BuildError, GEOMETRY_UPDATE,
                      PLATFORM_LANGUAGE, PROPAGATION, actions_of, add_subject,
                      container, layout, new_comment, new_element,
                      new_transition)
from .notation import (Comment, Issue, Subject, Transition, INITIAL, MACHINE,
                       STATE, PATH, UNNAMED, SUBJECT_ELEMENT, SUBJECT_NAME,
                       SUBJECT_BODY, language_spelling)
from .reader import decode

COMMENT_TYPES = [CyberiadaML.elementComment, CyberiadaML.elementFormalComment]
# the text estimates of libcyberiadaml: a 16 px monospace font
CHAR_WIDTH, LINE_HEIGHT, TEXT_MARGIN = 10.0, 20.0, 8.0
ACTION_HEAD, GUARD_EXTRA = 6, 3     # "entry/", " [" and "]"
SUBJECT_KINDS = {CyberiadaML.commentSubjectElement: SUBJECT_ELEMENT,
                 CyberiadaML.commentSubjectName: SUBJECT_NAME,
                 CyberiadaML.commentSubjectData: SUBJECT_BODY}
LABEL_LIMIT = 40


class Change:
    """One change of the document: the code of the message and the id of
    the element in the result."""

    def __init__(self, code, element=None, **fields):
        self.code = code
        self.element = element
        self.fields = fields

    def __repr__(self):
        return 'Change({!r}, {!r}, {!r})'.format(self.code, self.element,
                                                 self.fields)


class PatchError(Exception):
    """The changed tree names the old one wrongly."""

    def __init__(self, issues):
        super().__init__(', '.join(i.code for i in issues))
        self.issues = issues


def _normal(text):
    """A text as the notation reads it: no comment lines, dedented."""
    lines = [line.rstrip() for line in (text or '').split('\n')
             if not line.strip().startswith('#')]
    return textwrap.dedent('\n'.join(lines)).strip()


def same_text(old, new):
    return (old or '') == (new or '') or _normal(old) == _normal(new)


def _guard(text):
    return ' '.join((text or '').split())


def _unquoted(path):
    return PATH.join(p[1:-1] if p.startswith('"') else p
                     for p in path.split(PATH))


def _entries(vertex):
    """The actions of a state as comparable entries."""
    entries = [(b.kind, '', '', '', b.action) for b in vertex.behaviours]
    entries.extend(('', t.event, _guard(t.guard), t.propagation, t.action)
                   for t in vertex.internals)
    return entries


def text_size(vertex):
    """The estimated text block of a state: the title, the actions as the
    writer formats them."""
    chars, lines = len(vertex.name or ''), 1
    for kind, event, guard, _, action in _entries(vertex):
        head = ACTION_HEAD if kind else \
            len(event) + 1 + (len(guard) + GUARD_EXTRA if guard else 0)
        chars = max(chars, head)
        lines += 1
        for line in action.split('\n') if action else []:
            chars = max(chars, len(line))
            lines += 1
    return (chars * CHAR_WIDTH + 2 * TEXT_MARGIN,
            lines * LINE_HEIGHT + 2 * TEXT_MARGIN)


def comment_body(text):
    """A comment text as the notation reads it back: dedented, no trailing
    spaces, no blank lines around it."""
    lines = [line.rstrip() for line in
             (text or '').replace('\r\n', '\n').split('\n')]
    return textwrap.dedent('\n'.join(lines)).strip('\n')


def comment_size(title, body):
    """The estimated text block of a comment: its title over its text."""
    lines = body.split('\n') if body else []
    if title:
        lines.append(title)
    chars = max([len(line) for line in lines] + [0])
    return (chars * CHAR_WIDTH + 2 * TEXT_MARGIN,
            len(lines) * LINE_HEIGHT + 2 * TEXT_MARGIN)


def _comment_label(comment):
    """The name of a comment in the change list: its title, else the start
    of its text."""
    if comment.name and not comment.unnamed:
        return comment.name
    text = ' '.join(comment_body(comment.body).split())
    return text if len(text) <= LABEL_LIMIT else \
        text[:LABEL_LIMIT - 3] + '...'


def _label(transition):
    text = '{} -> {}'.format(transition.source.name or transition.source.kind,
                             transition.target.name or transition.target.kind)
    return '{}: {}'.format(transition.event, text) if transition.event \
        else text


class _Patch:
    def __init__(self, document, old, new):
        self.document = document
        self.old = old
        self.new = new
        self.match = {}      # id(new vertex) -> old vertex
        self.claimed = {}    # id(old vertex) -> new vertex
        self.created = {}    # id(new vertex) -> element id in the document
        self.changes = []
        self.issues = []
        self.texts = {}      # old id -> (new, old): the texts changed
        self.transition_ids = {}   # id(new transition) -> element id
        self.notes = []      # (new, old) comments whose texts changed

    # the identity

    def _bind(self, new, old):
        self.match[id(new)] = old
        self.claimed[id(old)] = new

    def _old_path(self, new_parent):
        """The path in the old machine of a new vertex's children."""
        if new_parent.kind == MACHINE:
            return ''
        old = self.match.get(id(new_parent))
        return old.path if old is not None else None

    def _find_old(self, vertex, index):
        if vertex.was is not None:
            was = _unquoted(vertex.was)
            if PATH not in was:
                parent = self._old_path(vertex.parent)
                was = (parent + PATH if parent else '') + was \
                    if parent is not None else None
            old = index.get(was) if was is not None else None
            if old is None:
                self.issues.append(Issue('U03', vertex.line, old=vertex.was))
            return old
        parent = self._old_path(vertex.parent)
        if parent is None:
            return None
        return index.get((parent + PATH if parent else '') + vertex.name)

    def _by_name(self, vertex, names):
        """The one unclaimed old vertex of the kind and the name: a vertex
        moved without (was OLD)."""
        found = [o for o in names.get(vertex.name, ())
                 if o.kind == vertex.kind and id(o) not in self.claimed]
        return found[0] if len(found) == 1 else None

    def match_vertex(self, vertex, old_machine, index, names=None):
        """Match by the path or (was OLD); with `names`, the second pass,
        by the unique name too."""
        if id(vertex) in self.match or old_machine is None:
            return
        if vertex.kind == INITIAL:
            parent = self.match.get(id(vertex.parent)) \
                if vertex.parent.kind != MACHINE else old_machine
            old = next((c for c in parent.children if c.kind == INITIAL),
                       None) if parent is not None else None
        elif vertex.was is not None and names is not None:
            return
        else:
            old = self._find_old(vertex, index)
            if old is None and names is not None and vertex.was is None:
                old = self._by_name(vertex, names)
        if old is None or old.kind != vertex.kind:
            return
        if id(old) in self.claimed:
            if vertex.was is not None:
                self.issues.append(Issue('U04', vertex.line, old=vertex.was,
                                         first=self.claimed[id(old)].line))
            return
        self._bind(vertex, old)

    def match_all(self):
        machines = {m.name: m for m in self.old.machines}
        for machine in self.new.machines:
            old = machines.get(_unquoted(machine.was) if machine.was
                               else machine.name)
            if old is None and machine.was is not None:
                self.issues.append(Issue('U03', machine.line,
                                         old=machine.was))
            if old is not None and id(old) not in self.claimed:
                self._bind(machine, old)
        for second in (False, True):
            for machine in self.new.machines:
                old_machine = self.match.get(id(machine))
                index, names = {}, {}
                if old_machine is not None:
                    for old in old_machine.walk():
                        if old.kind not in (MACHINE, INITIAL):
                            index[old.path] = old
                            names.setdefault(old.name, []).append(old)
                if old_machine is None and not second:
                    for vertex in machine.walk():
                        if vertex.was is not None and vertex is not machine:
                            self.issues.append(Issue('U03', vertex.line,
                                                     old=vertex.was))
                for vertex in machine.walk():
                    if vertex is not machine:
                        self.match_vertex(vertex, old_machine, index,
                                          names if second else None)
        for machine in self.new.machines:
            self.match_comments(machine)
        self.unnamed_names()

    def unnamed_names(self):
        """A `_` name refers to an unnamed element of the old diagram."""
        for item in list(self.new.walk()) + list(self.new.comments()):
            old = self.match.get(id(item))
            if item.name and item.name.startswith(UNNAMED) and \
               (old is None or not old.unnamed):
                self.issues.append(Issue('U02', item.line, name=item.name))

    def match_comments(self, machine):
        """A comment by its name or (was OLD) in its machine, else by its
        unchanged text."""
        old_machine = self.match.get(id(machine))
        olds = [c for v in old_machine.walk() for c in v.comments] \
            if old_machine is not None else []
        names = {c.name: c for c in olds}
        news = [c for v in machine.walk() for c in v.comments]
        for comment in news:
            key = comment.was if comment.was is not None else comment.name
            if key is None:
                continue
            old = names.get(_unquoted(key))
            if old is None:
                if comment.was is not None:
                    self.issues.append(Issue('U03', comment.line,
                                             old=comment.was))
            elif id(old) in self.claimed:
                if comment.was is not None:
                    self.issues.append(Issue('U04', comment.line,
                                             old=comment.was,
                                             first=self.claimed[id(old)].line))
            else:
                self._bind(comment, old)
        for comment in news:
            if id(comment) in self.match:
                continue
            for old in olds:
                if id(old) not in self.claimed and \
                   comment_body(old.body) == comment_body(comment.body):
                    self._bind(comment, old)
                    break

    # the document

    def element(self, vertex):
        """The element of a vertex of the new tree in the document."""
        old = self.match.get(id(vertex))
        element_id = old.element_id if old is not None \
            else self.created[id(vertex)]
        return self.document.find_element_by_id(element_id)

    def document_comments(self):
        for machine in self.document.get_state_machines():
            yield from machine.find_elements_by_types(COMMENT_TYPES)

    def detach(self, ids):
        """Remove the comment links to the elements; return them."""
        links = []
        for comment in self.document_comments():
            subjects = comment.get_subjects()
            for index in range(len(subjects) - 1, -1, -1):
                subject = subjects[index]
                element = subject.get_element()
                if element is not None and element.get_id() in ids:
                    links.append((comment.get_id(), subject.get_type(),
                                  subject.get_fragment(), element.get_id()))
                    comment.remove_subject(index)
        return links

    def attach(self, links):
        for comment_id, kind, fragment, element_id in links:
            comment = self.document.find_element_by_id(comment_id)
            element = self.document.find_element_by_id(element_id)
            if comment is None or element is None:
                continue
            if kind == CyberiadaML.commentSubjectName:
                self.document.add_comment_to_element_name(comment, element,
                                                          fragment)
            elif kind == CyberiadaML.commentSubjectData:
                self.document.add_comment_to_element_body(comment, element,
                                                          fragment)
            else:
                self.document.add_comment_to_element(comment, element)

    def transitions(self):
        """The pairs of the old and the new transitions, the removed old
        ones and the added new ones. A transition that keeps its ends but
        changes its event, guard or flag is the same one edited in place:
        it keeps its route."""
        def ident(vertex):
            old = self.match.get(id(vertex))
            return ('old', old.element_id) if old is not None \
                else ('new', id(vertex))

        olds = {}
        for vertex in self.old.walk():
            for transition in vertex.transitions:
                key = (('old', vertex.element_id), transition.event,
                       _guard(transition.guard), transition.propagation,
                       ('old', transition.target.element_id))
                olds.setdefault(key, []).append(transition)
        pairs, rest = [], []
        for vertex in self.new.walk():
            for transition in vertex.transitions:
                key = (ident(vertex), transition.event,
                       _guard(transition.guard), transition.propagation,
                       ident(transition.target))
                if olds.get(key):
                    pairs.append((olds[key].pop(0), transition))
                else:
                    rest.append(transition)
        ends = {}
        for group in olds.values():
            for transition in group:
                ends.setdefault((transition.source.element_id,
                                 transition.target.element_id),
                                []).append(transition)
        added = []
        for transition in rest:
            old_source = self.match.get(id(transition.source))
            old_target = self.match.get(id(transition.target))
            same = ends.get((old_source.element_id, old_target.element_id)) \
                if old_source is not None and old_target is not None else None
            if same:
                pairs.append((same.pop(0), transition))
            else:
                added.append(transition)
        removed = [t for group in ends.values() for t in group]
        return pairs, removed, added

    def apply(self):
        """The phases in their order: what goes, what comes, what moves."""
        removed = [v for v in self.old.walk() if id(v) not in self.claimed]
        moved = [(v, self.match[id(v)]) for v in self.new.walk()
                 if id(v) in self.match and v.kind != MACHINE and
                 self.match.get(id(v.parent)) is not self.match[id(v)].parent]
        pairs, gone, added = self.transitions()
        for old, new in pairs:
            self.transition_ids[id(new)] = old.element_id
        removed_ids = {v.element_id for v in removed}
        removed_ids.update(t.element_id for t in gone)
        self.detach(removed_ids)
        links = self.detach({o.element_id for _, old in moved
                             for o in old.walk()})
        self.remove_transitions(gone)
        self.add_vertices(self.add_machines())
        self.move(moved)
        self.remove_vertices(removed)
        self.rename_and_act()
        self.add_transitions(added)
        for old, new in pairs:
            if (old.event, _guard(old.guard), old.propagation) != \
               (new.event, _guard(new.guard), new.propagation) or \
               not same_text(old.action, new.action):
                self.update_action(old, new)
        self.attach(links)
        self.edit_comments()
        self.grow()
        self.meta()

    def remove_transitions(self, gone):
        for transition in gone:
            machine = self.document.find_element_by_id(
                transition.source.machine.element_id)
            machine.remove_element(transition.element_id)
            self.changes.append(Change('C07', label=_label(transition)))

    def add_machines(self):
        """The new machines; return the element ids of all machines."""
        machine_ids = {}
        for machine in self.new.machines:
            if id(machine) not in self.match:
                element = self.document.new_state_machine(machine.name)
                self.created[id(machine)] = element.get_id()
                self.changes.append(Change('C01', element.get_id(),
                                           kind=MACHINE, name=machine.name))
            machine_ids[machine.name] = self.element(machine).get_id()
        return machine_ids

    def add_vertices(self, machine_ids):
        for vertex in self.new.walk():
            if vertex.kind == MACHINE or id(vertex) in self.match:
                continue
            element = new_element(self.document, vertex,
                                  self.element(vertex.parent), machine_ids)
            for action in actions_of(vertex):
                element.add_action(action)
            self.created[id(vertex)] = element.get_id()
            self.changes.append(Change('C01', element.get_id(),
                                       kind=vertex.kind,
                                       name=vertex.name or ''))

    def move(self, moved):
        """Move by a copy into the new parent; the geometry is laid out
        anew, unless the parent is new and gets the moved ones all from one
        old parent: then the drawing goes into it as it is (a wrap)."""
        wraps = {}
        for vertex, old in moved:
            if id(vertex.parent) in self.created:
                wraps.setdefault(id(vertex.parent), set()).add(id(old.parent))
        for vertex, old in moved:
            element = self.document.find_element_by_id(old.element_id)
            source = self.document.find_element_by_id(old.parent.element_id)
            target = self.element(vertex.parent)
            copy = element.copy(target)
            source.remove_element(old.element_id)
            target.add_element(copy)
            if len(wraps.get(id(vertex.parent), ())) != 1:
                copy.clean_geometry()
            self.changes.append(Change('C04', old.element_id, name=vertex.name,
                                       parent=vertex.parent.name))

    def grow(self):
        """A drawn simple state or comment whose text grew grows from its
        corner by the estimate of what it gained; the layout keeps the ends
        of its routes and links on the new border."""
        grown = []
        sizes = [(old.element_id, CyberiadaML.elementSimpleState,
                  text_size(old), text_size(vertex))
                 for vertex, old in self.texts.values()]
        sizes.extend((old.element_id, CyberiadaML.elementComment,
                      comment_size(old.title, comment_body(old.body)),
                      comment_size(title, comment_body(comment.body)))
                     for title, comment, old in self.notes)
        for element_id, kind, (w0, h0), (w1, h1) in sizes:
            element = self.document.find_element_by_id(element_id)
            if element is None or not element.has_geometry() or \
               element.get_type() != kind:
                continue
            if w1 > w0 or h1 > h0:
                grown.append((element_id, max(w1 - w0, 0.0),
                              max(h1 - h0, 0.0)))
        if not grown:
            return
        # the corner is fixed in the local format, not in the centred one
        fmt = self.document.get_geometry_format()
        self.document.convert_geometry(CyberiadaML.geometryFormatCyberiada10)
        for element_id, dw, dh in grown:
            element = self.document.find_element_by_id(element_id)
            rect = element.get_geometry_rect()
            element.update_geometry(CyberiadaML.Rect(
                rect.x, rect.y, rect.width + dw, rect.height + dh))
        self.document.convert_geometry(fmt)

    def remove_vertices(self, removed):
        """Remove the topmost removed vertices with their subtrees."""
        for old in removed:
            if old.parent is not None and id(old.parent) not in self.claimed:
                continue
            if old.kind == MACHINE:
                self.document.remove_element(old.element_id)
            else:
                self.document.find_element_by_id(old.parent.element_id) \
                    .remove_element(old.element_id)
            self.changes.append(Change('C02', kind=old.kind,
                                       name=old.name or ''))

    def add_transitions(self, added):
        for transition in added:
            element = new_transition(self.document,
                                     self.element(transition.source.machine),
                                     transition,
                                     self.element(transition.source),
                                     self.element(transition.target))
            self.transition_ids[id(transition)] = element.get_id()
            self.changes.append(Change('C06', element.get_id(),
                                       label=_label(transition)))

    # the comments

    def target_id(self, target):
        """The element id of a subject of the new tree."""
        if isinstance(target, Transition):
            return self.transition_ids.get(id(target))
        if isinstance(target, Comment):
            return self.created.get(id(target)) or \
                self.match[id(target)].element_id
        return self.element(target).get_id()

    def edit_comments(self):
        """Remove the comments that went, create the new ones, edit the
        texts and the titles, then link: what stays keeps its geometry."""
        for old in self.old.comments():
            if id(old) in self.claimed or \
               self.document.find_element_by_id(old.element_id) is None:
                continue
            self.document.find_element_by_id(old.parent_element_id) \
                .remove_element(old.element_id)
            self.changes.append(Change('C10', name=_comment_label(old)))
        fresh = []
        for comment in self.new.comments():
            old = self.match.get(id(comment))
            element = self.document.find_element_by_id(old.element_id) \
                if old is not None else None
            if element is None:
                element = new_comment(self.document, comment, self.element(
                    container(comment.parent)))
                self.created[id(comment)] = element.get_id()
                self.changes.append(Change('C09', element.get_id(),
                                           name=_comment_label(comment)))
                fresh.append(comment)
            else:
                self.edit_comment(comment, old, element)
        for comment in fresh:
            element = self.document.find_element_by_id(
                self.created[id(comment)])
            for subject in comment.subjects:
                add_subject(self.document, element, subject,
                            self.document.find_element_by_id(
                                self.target_id(subject.target)))
        for comment in self.new.comments():
            old = self.match.get(id(comment))
            if old is not None and id(comment) not in self.created:
                self.relink(comment, old)

    def edit_comment(self, comment, old, element):
        title = old.title if comment.name == old.name or \
            (comment.name or '').startswith(UNNAMED) else comment.name
        changed = False
        if (title or '') != (old.title or ''):
            element.set_name(title or '')
            changed = True
        if comment_body(comment.body) != comment_body(old.body):
            element.set_body(comment.body)
            changed = True
        if changed:
            self.notes.append((title, comment, old))
            self.changes.append(Change('C11', old.element_id,
                                       name=_comment_label(comment)))

    def relink(self, comment, old):
        """The links of a kept comment: those the notation shows are
        compared, the others stay."""
        shown = [(s.element_id, s.kind, s.fragment) for s in old.subjects]
        wanted = [(self.target_id(s.target), s.kind, s.fragment)
                  for s in comment.subjects]
        gone = [key for key in shown if key not in wanted]
        come = [key for key in wanted if key not in shown]
        if not gone and not come:
            return
        element = self.document.find_element_by_id(old.element_id)
        subjects = element.get_subjects()
        for index in range(len(subjects) - 1, -1, -1):
            linked = subjects[index].get_element()
            key = (linked.get_id() if linked is not None else None,
                   SUBJECT_KINDS.get(subjects[index].get_type()),
                   subjects[index].get_fragment() or '')
            if key in gone:
                element.remove_subject(index)
                gone.remove(key)
        for target_id, kind, fragment in come:
            add_subject(self.document, element, Subject(kind, fragment),
                        self.document.find_element_by_id(target_id))
        self.changes.append(Change('C12', old.element_id,
                                   name=_comment_label(comment)))

    def rename_and_act(self):
        for vertex in self.new.walk():
            old = self.match.get(id(vertex))
            if old is None:
                continue
            element = self.element(vertex)
            if vertex.name != old.name:
                element.set_name(vertex.name)
                self.texts[old.element_id] = (vertex, old)
                self.changes.append(Change('C03', old.element_id,
                                           old=old.name, name=vertex.name))
            if vertex.kind == STATE:
                self.act(vertex, old, element)

    def act(self, vertex, old, element):
        olds, news = _entries(old), _entries(vertex)
        if len(olds) == len(news) and all(
                o[:4] == n[:4] and same_text(o[4], n[4])
                for o, n in zip(olds, news)):
            return
        # an action unchanged but for the notation keeps its original text
        texts = {}
        for entry in olds:
            texts.setdefault(entry[:4], []).append(entry[4])
        for behaviour in vertex.behaviours:
            for text in texts.get((behaviour.kind, '', '', ''), []):
                if same_text(text, behaviour.action):
                    behaviour.action = text
        for transition in vertex.internals:
            key = ('', transition.event, _guard(transition.guard),
                   transition.propagation)
            for text in texts.get(key, []):
                if same_text(text, transition.action):
                    transition.action = text
        element.set_actions(actions_of(vertex))
        self.texts[old.element_id] = (vertex, old)
        self.changes.append(Change('C05', old.element_id, name=vertex.name))

    def update_action(self, old, new):
        element = self.document.find_element_by_id(old.element_id)
        action = element.get_action()
        if new.event or new.guard or new.action or new.propagation:
            action.update(new.event, new.guard, new.action,
                          PROPAGATION[new.propagation])
        else:
            action.clear()
        self.changes.append(Change('C08', old.element_id, label=_label(new)))

    def meta(self):
        meta = self.document.meta()
        if (self.new.name or '') != (self.old.name or ''):
            self.document.set_name(self.new.name or '')
        if not same_text(self.old.description, self.new.description):
            if self.new.description:
                meta.set_string('description', self.new.description)
            else:
                meta.remove_string('description')
        # a missing language: header keeps the language of the diagram
        if self.new.language and language_spelling(self.new.language) != \
                language_spelling(self.old.language):
            meta.set_string(PLATFORM_LANGUAGE, self.new.language)


def patch(graphml, old, new, geometry=GEOMETRY_UPDATE):
    """Apply the analysed changed tree `new` to a fresh decode of the
    document `old` was read from; lay it out. Return (document, changes)."""
    document = decode(graphml)
    work = _Patch(document, old, new)
    work.match_all()
    if work.issues:
        raise PatchError(sorted(work.issues, key=lambda i: i.line or 0))
    try:
        work.apply()
    except BINDING_ERRORS as error:
        raise BuildError([Issue('B01', message=str(error))]) from error
    layout(document, geometry)
    return document, work.changes
