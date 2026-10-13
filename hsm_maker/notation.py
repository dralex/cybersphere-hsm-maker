# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The notation: the tree, the parser and the checks
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

"""The text a model writes for the maker (docs/NOTATION.md): a line is an
element, the indentation is the nesting, a transition names its target."""

import difflib
import re
import textwrap

MACHINE = 'machine'
STATE = 'state'
INITIAL = 'initial'
FINAL = 'final'
TERMINATE = 'terminate'
CHOICE = 'choice'

ERROR = 'error'
WARNING = 'warning'

BLOCKS = (MACHINE, STATE, CHOICE)
KEYWORDS = (MACHINE, STATE, INITIAL, FINAL, TERMINATE, CHOICE)
NAMED = (STATE, FINAL, TERMINATE, CHOICE)
RESERVED = ('entry', 'exit', 'do', 'propagate', 'block', 'defer', 'else')
HEADERS = ('name', 'description')
ELSE = 'else'
PATH = '::'
KNOWN_LIMIT = 12

WORD_RE = re.compile(r'\w+\Z')
EVENT_RE = re.compile(r'\w(?:[\w .]*\w)?(?:\(\w+\))?\Z')
NAME = r'(?:\w+|"[^"\n]*")'
TARGET_RE = re.compile(NAME + r'(?:::' + NAME + r')*')
BLOCK_RE = re.compile(r'(?:machine|state|choice)(?:\s|\Z)')
HEADER_RE = re.compile(r'(name|description):(.*)\Z', re.S)
BEHAVIOUR_RE = re.compile(r'(entry|exit)\s*/(.*)\Z', re.S)
DO_RE = re.compile(r'do\s*/')
DEFER_RE = re.compile(r'defer\b')
FENCE_RE = re.compile(r'^[ \t]*```[^\n]*\n(.*?)(?:^[ \t]*```[ \t]*$|\Z)',
                      re.S | re.M)


class Issue:
    """An issue of a text: the code of docs/NOTATION.md, the line and the
    fields of the message."""

    def __init__(self, code, line=None, severity=ERROR, **fields):
        self.code = code
        self.line = line
        self.severity = severity
        self.fields = fields

    def __repr__(self):
        return 'Issue({!r}, {!r}, {!r})'.format(self.code, self.line,
                                                self.fields)


class NotationError(Exception):
    """The syntax errors of a text."""

    def __init__(self, issues):
        super().__init__(', '.join(i.code for i in issues))
        self.issues = issues


class Vertex:
    """A machine, a state or a pseudostate."""

    def __init__(self, kind, name, line, parent=None):
        self.kind = kind
        self.name = name
        self.line = line
        self.parent = parent
        self.children = []
        self.behaviours = []
        self.internals = []
        self.transitions = []
        if parent is not None:
            parent.children.append(self)

    @property
    def machine(self):
        vertex = self
        while vertex.parent is not None:
            vertex = vertex.parent
        return vertex

    @property
    def path(self):
        """The qualified name in the machine, as the binding writes it."""
        names = []
        vertex = self
        while vertex.parent is not None:
            names.append(vertex.name or '')
            vertex = vertex.parent
        return PATH.join(reversed(names))

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def inside(self, other):
        """Whether this vertex is `other` or nested in it."""
        vertex = self
        while vertex is not None:
            if vertex is other:
                return True
            vertex = vertex.parent
        return False

    def __repr__(self):
        return 'Vertex({}, {!r}, line {})'.format(self.kind, self.name,
                                                  self.line)


class Behaviour:
    """The entry or the exit behaviour of a state."""

    def __init__(self, kind, action, line):
        self.kind = kind
        self.action = action
        self.line = line


class Transition:
    """A transition, internal when it has no target."""

    def __init__(self, line, source, event='', guard='', action='',
                 target_ref=None):
        self.line = line
        self.source = source
        self.event = event
        self.guard = guard
        self.action = action
        self.target_ref = target_ref
        self.target = None


class Diagram:
    """The tree of one document."""

    def __init__(self):
        self.name = None
        self.description = None
        self.machines = []

    def walk(self):
        for machine in self.machines:
            yield from machine.walk()


def extract(answer):
    """The first fenced block of a model answer, else the whole answer."""
    match = FENCE_RE.search(answer)
    return match.group(1) if match else answer


class _Line:
    """A logical line: a line with its continuation lines."""

    def __init__(self, number, indent, text):
        self.number = number
        self.indent = indent
        self.first = text
        self.rest = []

    @property
    def text(self):
        if not self.rest:
            return self.first
        return self.first + '\n' + textwrap.dedent('\n'.join(self.rest))


class _Fail(Exception):
    def __init__(self, code, **fields):
        super().__init__(code)
        self.code = code
        self.fields = fields


def _lines(text, issues):
    lines = []
    text = text.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')
    for number, raw in enumerate(text.split('\n'), 1):
        raw = raw.rstrip()
        body = raw.lstrip(' \t')
        if not body or body.startswith('#'):
            continue
        margin = raw[:len(raw) - len(body)]
        if '\t' in margin:
            issues.append(Issue('N01', number))
            continue
        indent = len(margin)
        last = lines[-1] if lines else None
        if last is not None and indent > last.indent and \
           not BLOCK_RE.match(last.first):
            last.rest.append(raw)
        else:
            lines.append(_Line(number, indent, body))
    return lines


def _name(text, keyword):
    text = text.strip()
    if not text:
        raise _Fail('N07', keyword=keyword)
    if text.startswith('"'):
        if len(text) < 2 or not text.endswith('"'):
            raise _Fail('N08')
        name = text[1:-1]
        if not name or name != name.strip() or '"' in name:
            raise _Fail('N06', text=text)
    else:
        name = text
        if not WORD_RE.match(name):
            if PATH in name:
                raise _Fail('N09', text=name)
            raise _Fail('N06', text=name)
    if PATH in name:
        raise _Fail('N09', text=name)
    return name


def _skip(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _split(text):
    """EVENT [GUARD] -> TARGET / ACTION: (event, guard, target, action);
    the absent parts are None, the event is '' when absent."""
    end = len(text)
    i = 0
    while i < end and text[i] not in '[/' and not text.startswith('->', i):
        i += 1
    event = text[:i].strip()
    i = _skip(text, i)
    guard = None
    if i < end and text[i] == '[':
        k = i + 1
        while k < end and text[k] != ']':
            if text[k] == '\\' and k + 1 < end and text[k + 1] in '[]':
                k += 2
                continue
            if text[k] == '[':
                raise _Fail('N16')
            k += 1
        if k >= end:
            raise _Fail('N15')
        guard = ' '.join(text[i + 1:k].split())
        if not guard:
            raise _Fail('N17')
        i = _skip(text, k + 1)
    target = None
    if text.startswith('->', i):
        i = _skip(text, i + 2)
        match = TARGET_RE.match(text, i)
        if not match:
            raise _Fail('N18')
        target = match.group(0)
        i = _skip(text, match.end())
    action = None
    if i < end and text[i] == '/':
        action = text[i + 1:].strip()
        i = end
    if i < end:
        raise _Fail('N20', text=text[i:].split('\n')[0])
    if action and DEFER_RE.match(action):
        raise _Fail('N23')
    return event, guard, target, action


def _event(event):
    if not event:
        return
    if not EVENT_RE.match(event):
        raise _Fail('N13', event=event)
    for word in event.split():
        if word in RESERVED:
            raise _Fail('N14', event=event, word=word)


def _header(diagram, line, key, value, issues):
    if diagram.machines or getattr(diagram, key) is not None:
        issues.append(Issue('N27', line.number, header=key + ':'))
        return
    value = value.strip()
    if not value:
        issues.append(Issue('N28', line.number, header=key + ':'))
        return
    setattr(diagram, key, value)


def _transition(parent, line, text):
    event, guard, target, action = _split(text)
    _event(event)
    if parent.kind == CHOICE:
        if event or target is None:
            raise _Fail('N12')
        if guard is None:
            raise _Fail('N25')
    elif parent.kind != STATE:
        raise _Fail('N10')
    elif target is None:
        if not event:
            raise _Fail('N29')
        if action is None:
            raise _Fail('N19', event=event)
        parent.internals.append(Transition(line.number, parent, event,
                                           guard or '', action))
        return
    parent.transitions.append(Transition(line.number, parent, event,
                                         guard or '', action or '', target))


def _declaration(diagram, stack, line, parent, keyword):
    first, _, rest = line.text.partition('\n')
    if rest:
        raise _Fail('N26', keyword=keyword, name=first[len(keyword):].strip(),
                    text=rest.split('\n')[0].strip())
    name = _name(first[len(keyword):], keyword)
    if keyword == MACHINE:
        if parent is not None:
            raise _Fail('N03')
        vertex = Vertex(MACHINE, name, line.number)
        diagram.machines.append(vertex)
    elif parent.kind == CHOICE:
        raise _Fail('N12')
    else:
        vertex = Vertex(keyword, name, line.number, parent)
    if keyword in BLOCKS:
        stack.append((line.indent, vertex))


def _initial(parent, line):
    if parent.kind == CHOICE:
        raise _Fail('N12')
    event, guard, target, action = _split(line.text[len(INITIAL):])
    if event or guard is not None or target is None:
        raise _Fail('N24')
    vertex = Vertex(INITIAL, None, line.number, parent)
    vertex.transitions.append(Transition(line.number, vertex, '', '',
                                         action or '', target))


def _behaviour(parent, line, match):
    if parent.kind != STATE:
        raise _Fail('N11')
    action = match.group(2).strip()
    if not action:
        raise _Fail('N21', keyword=match.group(1) + '/')
    parent.behaviours.append(Behaviour(match.group(1), action, line.number))


def _statement(diagram, stack, line, issues):
    text = line.text
    while stack and stack[-1][0] >= line.indent:
        stack.pop()
    parent = stack[-1][1] if stack else None
    keyword = text.split(None, 1)[0] if text.split() else ''
    if parent is None:
        header = HEADER_RE.match(text)
        if header:
            _header(diagram, line, header.group(1), header.group(2), issues)
            return
        if keyword != MACHINE:
            raise _Fail('N02')
    if keyword in (MACHINE, STATE, CHOICE, FINAL, TERMINATE):
        _declaration(diagram, stack, line, parent, keyword)
    elif keyword == INITIAL or keyword.startswith(INITIAL + '->'):
        _initial(parent, line)
    elif DO_RE.match(text):
        raise _Fail('N22')
    elif BEHAVIOUR_RE.match(text):
        _behaviour(parent, line, BEHAVIOUR_RE.match(text))
    elif keyword in HEADERS or HEADER_RE.match(text):
        raise _Fail('N27', header=text.split(':', 1)[0] + ':')
    else:
        _transition(parent, line, text)


def parse(text):
    """Read the notation; return a Diagram or raise NotationError."""
    issues = []
    diagram = Diagram()
    stack = []
    for line in _lines(text, issues):
        try:
            _statement(diagram, stack, line, issues)
        except _Fail as fail:
            issues.append(Issue(fail.code, line.number, **fail.fields))
    if not diagram.machines and not any(i.code == 'N02' for i in issues):
        issues.append(Issue('N04'))
    if issues:
        raise NotationError(_ordered(issues))
    return diagram


def _ordered(issues):
    return sorted(issues, key=lambda i: (i.line or 0))


def _known(name, machine):
    paths = [v.path for v in machine.walk() if v.kind in NAMED]
    names = [v.name for v in machine.walk() if v.kind in NAMED]
    close = difflib.get_close_matches(name, paths + names)
    known = []
    for item in close + paths[:KNOWN_LIMIT]:
        if item not in known:
            known.append(item)
    return ', '.join(known[:KNOWN_LIMIT])


def _resolve(transition, issues):
    ref = transition.target_ref
    source = transition.source
    machine = source.machine
    parts = [p[1:-1] if p.startswith('"') else p for p in ref.split(PATH)]
    named = [v for v in machine.walk() if v.kind in NAMED]
    if len(parts) > 1:
        found = [v for v in named if v.path == PATH.join(parts)]
    else:
        level = source.parent
        while level is not None:
            near = [c for c in level.children
                    if c.kind in NAMED and c.name == parts[0]]
            if near:
                return near[0]
            level = level.parent
        found = [v for v in named if v.name == parts[0]]
    if len(found) == 1:
        return found[0]
    if found:
        issues.append(Issue('R02', transition.line, target=ref,
                            candidates=', '.join(v.path for v in found)))
    elif ref in KEYWORDS:
        issues.append(Issue('R03', transition.line, target=ref))
    elif ref == machine.name:
        issues.append(Issue('R04', transition.line, target=ref))
    else:
        issues.append(Issue('R01', transition.line, target=ref,
                            known=_known(ref, machine)))
    return None


def _level(vertex, issues):
    names = {}
    initial = None
    for child in vertex.children:
        if child.kind == INITIAL:
            if initial is not None:
                issues.append(Issue('S03', child.line, first=initial))
            else:
                initial = child.line
        elif child.name in names:
            issues.append(Issue('S02', child.line, name=child.name,
                                first=names[child.name]))
        else:
            names[child.name] = child.line
    seen = set()
    for behaviour in vertex.behaviours:
        if behaviour.kind in seen:
            issues.append(Issue('S06', behaviour.line,
                                keyword=behaviour.kind + '/',
                                name=vertex.name))
        seen.add(behaviour.kind)


def _transitions(machine, issues):
    incoming = {}
    for vertex in machine.walk():
        elses = 0
        for transition in vertex.transitions:
            if transition.guard == ELSE:
                elses += 1
                if elses == 2:
                    issues.append(Issue('S11', transition.line,
                                        name=vertex.path))
            target = _resolve(transition, issues)
            transition.target = target
            if target is None:
                continue
            if vertex.kind == INITIAL and (target is vertex.parent or
                                           not target.inside(vertex.parent)):
                issues.append(Issue('S07', transition.line))
                continue
            if target.kind == STATE and target.children and \
               not any(c.kind == INITIAL for c in target.children) and \
               (vertex is target or not vertex.inside(target)):
                issues.append(Issue('S08', transition.line,
                                    target=target.path))
            if target.kind == CHOICE:
                lines = incoming.setdefault(id(target), [])
                lines.append(transition.line)
                if len(lines) == 2:
                    issues.append(Issue('S10', transition.line,
                                        name=target.path,
                                        lines=', '.join(str(n) for n in lines)))
        if vertex.kind == CHOICE and len(vertex.transitions) < 2:
            issues.append(Issue('S09', vertex.line, name=vertex.path))


def _unreachable(machine):
    seen = set()
    todo = [t.target for v in machine.children if v.kind == INITIAL
            for t in v.transitions]
    while todo:
        vertex = todo.pop()
        if vertex is None or id(vertex) in seen:
            continue
        seen.add(id(vertex))
        todo.extend(t.target for t in vertex.transitions)
        for child in vertex.children:
            if child.kind == INITIAL:
                todo.extend(t.target for t in child.transitions)
        if vertex.parent is not None and vertex.parent.kind != MACHINE:
            todo.append(vertex.parent)
    return [v for v in machine.walk() if v.kind in NAMED and id(v) not in seen]


def analyze(diagram):
    """Resolve the targets and check the semantics; return the issues."""
    issues = []
    first = {}
    for machine in diagram.machines:
        if machine.name in first:
            issues.append(Issue('S01', machine.line, name=machine.name,
                                first=first[machine.name]))
        else:
            first[machine.name] = machine.line
        if not machine.children:
            issues.append(Issue('S05', machine.line, name=machine.name))
        elif not any(c.kind == INITIAL for c in machine.children):
            issues.append(Issue('S04', machine.line, name=machine.name))
        for vertex in machine.walk():
            _level(vertex, issues)
        _transitions(machine, issues)
    if not issues:
        for machine in diagram.machines:
            for vertex in _unreachable(machine):
                issues.append(Issue('W01', vertex.line, WARNING,
                                    name=vertex.path))
    return _ordered(issues)
