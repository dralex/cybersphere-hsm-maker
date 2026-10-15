# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The notation: the tree, the parser, the checks and the writer
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
HISTORY = 'history'
DEEP_HISTORY = 'deep history'
ENTRY_POINT = 'entry point'
EXIT_POINT = 'exit point'
SUBMACHINE = 'submachine'

ERROR = 'error'
WARNING = 'warning'

PROPAGATE = 'propagate'
BLOCK = 'block'
DEFER = 'defer'
FLAGS = (PROPAGATE, BLOCK)

BLOCKS = (MACHINE, STATE, CHOICE, SUBMACHINE)
PLAIN = (MACHINE, STATE, CHOICE, FINAL, TERMINATE)
HISTORIES = (HISTORY, DEEP_HISTORY)
POINTS = (ENTRY_POINT, EXIT_POINT)
TAILED = HISTORIES + POINTS
NAMED = (STATE, FINAL, TERMINATE, CHOICE, SUBMACHINE) + TAILED
KEYWORDS = (MACHINE, STATE, INITIAL, FINAL, TERMINATE, CHOICE, HISTORY,
            SUBMACHINE)
RESERVED = ('entry', 'exit', 'do', PROPAGATE, BLOCK, DEFER, 'else')
HEADERS = ('name', 'description', 'language')
# the code languages of the editor, in their spelling
CODE_LANGUAGES = ('C', 'C++', 'C#', 'Java', 'JavaScript', 'Python')
ELSE = 'else'
PATH = '::'
UNNAMED = '_'
KNOWN_LIMIT = 12
INDENT = '  '
CONTINUATION = '    '

WORD_RE = re.compile(r'\w+\Z')
EVENT_RE = re.compile(r'\w(?:[\w .]*\w)?(?:\(\w+\))?\Z')
NAME = r'(?:\w+|"[^"\n]*")'
TARGET_RE = re.compile(NAME + r'(?:::' + NAME + r')*')
BLOCK_RE = re.compile(r'(?:machine|state|choice|submachine)(?:\s|\Z)')
KIND_RE = re.compile(r'(deep\s+history|history|entry\s+point|exit\s+point|'
                     r'submachine|machine|state|choice|final|terminate)'
                     r'(?=\s|\Z)')
NAME_TOKEN_RE = re.compile(r'"[^"\n]*"?|[^\s(]+')
WAS_RE = re.compile(r'\(\s*was\s+([^)\n]*?)\s*\)')
OF_RE = re.compile(r'of\s+(\S.*)\Z')
FLAG_RE = re.compile(r'(propagate|block)(?=\s|->|/|\Z)')
HEADER_RE = re.compile(r'(name|description|language):(.*)\Z', re.S)
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

    @property
    def key(self):
        """The issue without its line: the same issue in another text."""
        return (self.code, tuple(sorted((k, str(v)) for k, v in
                                        self.fields.items()
                                        if k not in ('first', 'lines'))))

    def __repr__(self):
        return 'Issue({!r}, {!r}, {!r})'.format(self.code, self.line,
                                                self.fields)


class NotationError(Exception):
    """The syntax errors of a text."""

    def __init__(self, issues):
        super().__init__(', '.join(i.code for i in issues))
        self.issues = issues


class Vertex:
    """A machine, a state, a submachine, a pseudostate or a point."""

    def __init__(self, kind, name, line, parent=None):
        self.kind = kind
        self.name = name
        self.line = line
        self.parent = parent
        self.children = []
        self.behaviours = []
        self.internals = []
        self.transitions = []
        self.reference = None
        self.was = None
        self.element_id = None
        self.unnamed = False
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
                 target_ref=None, propagation=''):
        self.line = line
        self.source = source
        self.event = event
        self.guard = guard
        self.action = action
        self.target_ref = target_ref
        self.propagation = propagation
        self.target = None
        self.element_id = None


class Diagram:
    """The tree of one document."""

    def __init__(self):
        self.name = None
        self.description = None
        self.language = None
        self.machines = []
        self.notes = []

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


def _declared(text, keyword):
    """NAME [(was OLD)] at the start of the text: (name, was, the rest)."""
    text = text.lstrip()
    if not text:
        raise _Fail('N07', keyword=keyword)
    token = NAME_TOKEN_RE.match(text)
    name = _name(token.group(0), keyword)
    rest = text[token.end():]
    was = None
    match = WAS_RE.match(rest.lstrip())
    if match:
        was = match.group(1)
        if not was or TARGET_RE.fullmatch(was) is None:
            raise _Fail('N06', text=was)
        rest = rest.lstrip()[match.end():]
    return name, was, rest.strip()


def _skip(text, i):
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _guard(text, i):
    """The guard at text[i] == '[': (the guard, the index after it)."""
    end = len(text)
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
    return guard, k + 1


def _split(text):
    """EVENT [GUARD] [FLAG] -> TARGET / ACTION: (event, guard, flag, target,
    action); the absent parts are None, the event is '' when absent."""
    end = len(text)
    i = 0
    while i < end and text[i] not in '[/' and not text.startswith('->', i):
        i += 1
    event = text[:i].strip()
    flag = None
    words = event.split()
    if len(words) > 1 and words[-1] in FLAGS:
        flag = words[-1]
        event = event[:event.rfind(flag)].strip()
    i = _skip(text, i)
    guard = None
    if i < end and text[i] == '[':
        guard, i = _guard(text, i)
        i = _skip(text, i)
    match = FLAG_RE.match(text, i)
    if match and flag is None:
        flag = match.group(1)
        i = _skip(text, match.end())
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
    return event, guard, flag, target, action


def _event(event):
    if not event:
        return
    if not EVENT_RE.match(event):
        raise _Fail('N13', event=event)
    for word in event.split():
        if word in RESERVED:
            raise _Fail('N14', event=event, word=word)


def language_spelling(name):
    """The spelling of CODE_LANGUAGES of a name equal to one of them but
    for the case; else the name."""
    for known in CODE_LANGUAGES:
        if name and name.lower() == known.lower():
            return known
    return name


def _header(diagram, line, key, value, issues):
    if diagram.machines or getattr(diagram, key) is not None:
        issues.append(Issue('N27', line.number, header=key + ':'))
        return
    value = value.strip()
    if not value:
        issues.append(Issue('N28', line.number, header=key + ':'))
        return
    setattr(diagram, key, language_spelling(value) if key == 'language'
            else value)


def _transition(parent, line, text):
    event, guard, flag, target, action = _split(text)
    _event(event)
    if parent.kind == CHOICE:
        if event or flag or target is None:
            raise _Fail('N12')
        if guard is None:
            raise _Fail('N25')
    elif parent.kind not in (STATE, SUBMACHINE):
        raise _Fail('N10')
    propagation = flag or ''
    if action == DEFER:
        if target is not None or flag:
            raise _Fail('N31')
        propagation = DEFER
        action = ''
    elif action and DEFER_RE.match(action):
        raise _Fail('N23')
    if flag and not event:
        raise _Fail('N30')
    if target is None:
        if parent.kind == SUBMACHINE:
            raise _Fail('N33')
        if not event:
            raise _Fail('N29')
        if action is None:
            raise _Fail('N19', event=event)
        parent.internals.append(Transition(line.number, parent, event,
                                           guard or '', action, None,
                                           propagation))
        return
    parent.transitions.append(Transition(line.number, parent, event,
                                         guard or '', action or '', target,
                                         propagation))


def _tail(vertex, line, text, keyword):
    """The transition written on the line of a vertex: -> TARGET / ACTION;
    the transition of a point may wait for an event."""
    if not text:
        return
    event, guard, flag, target, action = _split(text)
    if target is None or (keyword not in POINTS and
                          (event or guard is not None or flag)):
        raise _Fail('N34', keyword=keyword)
    _event(event)
    if flag and not event:
        raise _Fail('N30')
    if action and DEFER_RE.match(action):
        raise _Fail('N23')
    vertex.transitions.append(Transition(line.number, vertex, event,
                                         guard or '', action or '', target,
                                         flag or ''))


def _declaration_parts(text, kind):
    """The name, the (was OLD), the tail and the reference of a declaration."""
    reference = None
    if kind in PLAIN:
        first, _, rest = text.partition('\n')
        if rest:
            raise _Fail('N26', keyword=kind, name=first.strip(),
                        text=rest.split('\n')[0].strip())
        name, was, tail = _declared(first, kind)
        if tail:
            raise _Fail('N06', text=first.strip())
    else:
        name, was, tail = _declared(text, kind)
        if kind == SUBMACHINE:
            match = OF_RE.match(tail)
            if not match:
                raise _Fail('N32')
            reference = _name(match.group(1), kind)
    return name, was, tail, reference


def _declaration(diagram, stack, line, parent, kind, prefix):
    name, was, tail, reference = _declaration_parts(line.text[prefix:], kind)
    if kind == MACHINE:
        if parent is not None:
            raise _Fail('N03')
        vertex = Vertex(MACHINE, name, line.number)
        diagram.machines.append(vertex)
    elif parent.kind == CHOICE:
        raise _Fail('N12')
    elif parent.kind == SUBMACHINE and kind not in POINTS:
        raise _Fail('N33')
    else:
        vertex = Vertex(kind, name, line.number, parent)
    vertex.was = was
    vertex.reference = reference
    if kind in TAILED:
        _tail(vertex, line, tail, kind)
    if kind in BLOCKS:
        stack.append((line.indent, vertex))


def _initial(parent, line):
    if parent.kind == CHOICE:
        raise _Fail('N12')
    if parent.kind == SUBMACHINE:
        raise _Fail('N33')
    event, guard, flag, target, action = _split(line.text[len(INITIAL):])
    if event or guard is not None or flag or target is None:
        raise _Fail('N24')
    vertex = Vertex(INITIAL, None, line.number, parent)
    vertex.transitions.append(Transition(line.number, vertex, '', '',
                                         action or '', target))


def _behaviour(parent, line, match):
    if parent.kind == SUBMACHINE:
        raise _Fail('N33')
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
    kind = KIND_RE.match(text)
    if parent is None:
        header = HEADER_RE.match(text)
        if header:
            _header(diagram, line, header.group(1), header.group(2), issues)
            return
        if keyword != MACHINE:
            raise _Fail('N02')
    if kind:
        _declaration(diagram, stack, line, parent,
                     ' '.join(kind.group(1).split()), kind.end())
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


def _find(source, ref):
    """The vertices a reference from the source names: the nearest level
    first, then the whole machine; [] when none."""
    machine = source.machine
    parts = [p[1:-1] if p.startswith('"') else p for p in ref.split(PATH)]
    named = [v for v in machine.walk() if v.kind in NAMED]
    if len(parts) > 1:
        return [v for v in named if v.path == PATH.join(parts)]
    level = source.parent
    while level is not None:
        near = [c for c in level.children
                if c.kind in NAMED and c.name == parts[0]]
        if near:
            return near[:1]
        level = level.parent
    return [v for v in named if v.name == parts[0]]


def _resolve(transition, issues):
    ref = transition.target_ref
    machine = transition.source.machine
    found = _find(transition.source, ref)
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


def _placed(vertex, child, issues):
    """The placement rules of a history and a point in their container."""
    if child.kind in HISTORIES and vertex.kind == MACHINE:
        issues.append(Issue('S12', child.line))
    if child.kind == ENTRY_POINT and vertex.kind == SUBMACHINE and \
       child.transitions:
        issues.append(Issue('S17', child.line))
    if child.kind == EXIT_POINT and vertex.kind == MACHINE and \
       child.transitions:
        issues.append(Issue('S18', child.line))


def _level(vertex, issues):
    first = {}
    for child in vertex.children:
        if child.kind == INITIAL:
            if INITIAL in first:
                issues.append(Issue('S03', child.line, first=first[INITIAL]))
            else:
                first[INITIAL] = child.line
            continue
        if child.kind in HISTORIES:
            if child.kind in first:
                issues.append(Issue('S13', child.line, keyword=child.kind,
                                    name=vertex.name, first=first[child.kind]))
            else:
                first[child.kind] = child.line
        if (NAMED, child.name) in first:
            issues.append(Issue('S02', child.line, name=child.name,
                                first=first[(NAMED, child.name)]))
        else:
            first[(NAMED, child.name)] = child.line
        _placed(vertex, child, issues)
    seen = set()
    for behaviour in vertex.behaviours:
        if behaviour.kind in seen:
            issues.append(Issue('S06', behaviour.line,
                                keyword=behaviour.kind + '/',
                                name=vertex.name))
        seen.add(behaviour.kind)


def _submachine(vertex, machines, issues):
    target = machines.get(vertex.reference)
    if target is None:
        issues.append(Issue('S14', vertex.line, name=vertex.name,
                            machine=vertex.reference))
        return
    if target is vertex.machine:
        issues.append(Issue('S15', vertex.line, name=vertex.name))
        return
    points = [c for c in target.children if c.kind in POINTS]
    for child in vertex.children:
        if child.kind not in POINTS:
            continue
        if not any(p.kind == child.kind and p.name == child.name
                   for p in points):
            issues.append(Issue('S16', child.line, point=child.name,
                                machine=target.name,
                                known=', '.join(p.name for p in points)))


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
    todo.extend(v for v in machine.children if v.kind == ENTRY_POINT)
    while todo:
        vertex = todo.pop()
        if vertex is None or id(vertex) in seen:
            continue
        seen.add(id(vertex))
        todo.extend(t.target for t in vertex.transitions)
        for child in vertex.children:
            if child.kind == INITIAL:
                todo.extend(t.target for t in child.transitions)
            elif child.kind == EXIT_POINT and vertex.kind == SUBMACHINE:
                todo.append(child)
        if vertex.parent is not None and vertex.parent.kind != MACHINE:
            todo.append(vertex.parent)
    return [v for v in machine.walk() if v.kind in NAMED and id(v) not in seen]


def _new_only(diagram, issues):
    for vertex in diagram.walk():
        if vertex.was is not None:
            issues.append(Issue('U01', vertex.line, old=vertex.was))
        if vertex.name and vertex.name.startswith(UNNAMED):
            issues.append(Issue('U02', vertex.line, name=vertex.name))


def analyze(diagram, changing=False):
    """Resolve the targets and check the semantics; return the issues."""
    issues = []
    first = {}
    machines = {}
    for machine in diagram.machines:
        if machine.name in first:
            issues.append(Issue('S01', machine.line, name=machine.name,
                                first=first[machine.name]))
        else:
            first[machine.name] = machine.line
            machines[machine.name] = machine
        if not machine.children:
            issues.append(Issue('S05', machine.line, name=machine.name))
        elif not any(c.kind == INITIAL for c in machine.children):
            issues.append(Issue('S04', machine.line, name=machine.name))
        for vertex in machine.walk():
            _level(vertex, issues)
        _transitions(machine, issues)
    for vertex in diagram.walk():
        if vertex.kind == SUBMACHINE:
            _submachine(vertex, machines, issues)
    if not changing:
        _new_only(diagram, issues)
    if not issues:
        for machine in diagram.machines:
            for vertex in _unreachable(machine):
                issues.append(Issue('W01', vertex.line, WARNING,
                                    name=vertex.path))
    return _ordered(issues)


def _written_name(name):
    return name if WORD_RE.match(name) else '"' + name + '"'


def _reference(transition):
    """The shortest text that names the target from the source."""
    target = transition.target
    if target is None:
        return transition.target_ref
    found = _find(transition.source, _written_name(target.name))
    if len(found) == 1 and found[0] is target:
        return _written_name(target.name)
    return PATH.join(_written_name(n) for n in target.path.split(PATH))


def _with_action(head, action, pad, lines):
    """A line ending with an action; the further action lines continue it."""
    action_lines = action.split('\n') if action else ['']
    lines.append(pad + (head + ' ' + action_lines[0]).rstrip())
    for rest in action_lines[1:]:
        lines.append(pad + CONTINUATION + rest if rest else '')


def _transition_text(transition, pad, lines, prefix=''):
    parts = [prefix] if prefix else []
    if transition.event:
        parts.append(transition.event)
    if transition.guard:
        parts.append('[' + transition.guard + ']')
    if transition.propagation in FLAGS:
        parts.append(transition.propagation)
    internal = transition.target is None and transition.target_ref is None
    if not internal:
        parts.append('-> ' + _reference(transition))
    head = ' '.join(parts)
    if transition.propagation == DEFER:
        lines.append(pad + head + ' / ' + DEFER)
    elif transition.action or internal:
        _with_action(head + ' /', transition.action, pad, lines)
    else:
        lines.append(pad + head)


def _declaration_text(vertex):
    name = _written_name(vertex.name) if vertex.name else ''
    if vertex.was:
        name += ' (was ' + vertex.was + ')'
    if vertex.kind == SUBMACHINE:
        return 'submachine {} of {}'.format(name,
                                            _written_name(vertex.reference))
    return vertex.kind + ' ' + name


def _render(vertex, depth, notes, lines):
    pad = INDENT * depth
    inner = INDENT * (depth + 1)
    if vertex.kind == INITIAL:
        _transition_text(vertex.transitions[0], pad, lines, INITIAL)
        return
    if vertex.kind in TAILED and vertex.transitions:
        _transition_text(vertex.transitions[0], pad, lines,
                         _declaration_text(vertex))
        return
    lines.append(pad + _declaration_text(vertex))
    for text in notes.get(id(vertex), []):
        lines.append(inner + '# note: ' + text)
    for behaviour in vertex.behaviours:
        _with_action(behaviour.kind + '/', behaviour.action, inner, lines)
    for transition in vertex.internals:
        _transition_text(transition, inner, lines)
    for child in vertex.children:
        _render(child, depth + 1, notes, lines)
    for transition in vertex.transitions:
        _transition_text(transition, inner, lines)


def render(diagram):
    """The notation text of a tree, the notes as `# note:` lines."""
    lines = []
    notes = {}
    for vertex, text in diagram.notes:
        notes.setdefault(id(vertex) if vertex is not None else None,
                         []).append(text)
    if diagram.name:
        _with_action('name:', diagram.name, '', lines)
    if diagram.description:
        _with_action('description:', diagram.description, '', lines)
    if diagram.language:
        _with_action('language:', diagram.language, '', lines)
    for text in notes.get(None, []):
        lines.append('# note: ' + text)
    for machine in diagram.machines:
        _render(machine, 0, notes, lines)
    return '\n'.join(lines) + '\n'
