# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the comments and their links in the notation
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

from hsm_maker.cyberiadaml import CyberiadaML
from conftest import chat_answer, fenced, validate
from test_editor_plugin import editor, model
from test_patcher import codes, drawn, states
from hsm_maker import builder as B
from hsm_maker import language as L
from hsm_maker import maker as M
from hsm_maker import notation as N
from hsm_maker import reader as R
from hsm_maker.patcher import Change

DOORS = '''machine Lift
  comment Floors (on Idle, Moving)
    The lift serves the calls in the order of the floors.

    # Why
    Fewer turns.
  initial -> Idle / floor = 1
  state Idle
    comment Waiting (on Moving)
      Written in a simple state.
    CALL [call_floor != floor] -> Moving
  state Moving
    FLOOR [floor == target] -> DoorsOpen
  state DoorsOpen
    entry/ open_doors()
    TIMEOUT -> Idle / close_doors()
  comment (on DoorsOpen TIMEOUT -> Idle, DoorsOpen "open_doors()", Idle name "Id", Floors)
    The doors stay open for **5 s**; "quoted", a, b.
'''

KINDS = {CyberiadaML.commentSubjectElement: N.SUBJECT_ELEMENT,
         CyberiadaML.commentSubjectName: N.SUBJECT_NAME,
         CyberiadaML.commentSubjectData: N.SUBJECT_BODY}


def comments_of(graphml):
    """The informal comments of a document by id: title, text, links."""
    document = CyberiadaML.Document()
    document.decode(graphml)
    found = {}
    for machine in document.get_state_machines():
        for comment in machine.find_elements_by_types(
                [CyberiadaML.elementComment]):
            found[comment.get_id()] = (
                comment.get_name(), comment.get_body(),
                [(s.get_element().get_id(), KINDS[s.get_type()],
                  s.get_fragment()) for s in comment.get_subjects()])
    return found


def issues(text, changing=False):
    try:
        return [(i.code, i.line) for i in
                N.analyze(N.parse(text), changing)]
    except N.NotationError as error:
        return [(i.code, i.line) for i in error.issues]


def test_parse_and_render():
    tree = N.parse(DOORS)
    assert N.analyze(tree) == []
    floors, doors, waiting = list(tree.comments())
    assert floors.body == 'The lift serves the calls in the order of the ' \
        'floors.\n\n# Why\nFewer turns.'
    assert waiting.parent.name == 'Idle'
    kinds = [(s.kind, s.fragment, type(s.target).__name__)
             for s in doors.subjects]
    assert kinds == [(N.SUBJECT_ELEMENT, '', 'Transition'),
                     (N.SUBJECT_BODY, 'open_doors()', 'Vertex'),
                     (N.SUBJECT_NAME, 'Id', 'Vertex'),
                     (N.SUBJECT_ELEMENT, '', 'Comment')]
    assert doors.body == 'The doors stay open for **5 s**; "quoted", a, b.'
    text = N.render(tree)
    again = N.parse(text)
    assert N.analyze(again) == []
    assert N.render(again) == text


def test_fragments_quoted():
    tree = N.parse('machine M\n  initial -> A\n  state A\n'
                   '    entry/ say("a, b")\n'
                   '  comment (on A "say(\\"a, b\\")")\n    quoted\n')
    assert N.analyze(tree) == []
    assert list(tree.comments())[0].subjects[0].fragment == 'say("a, b")'
    assert '(on A "say(\\"a, b\\")")' in N.render(tree)


@pytest.mark.parametrize('text, expected', [
    ('machine M\n  initial -> A\n  state A\n  comment (on B)\n    x\n',
     [('R05', 4)]),
    ('machine M\n  initial -> A\n  state A\n    E -> A\n    F -> A\n'
     '  comment (on A -> A)\n    x\n', [('R06', 6)]),
    ('machine M\n  initial -> A\n  state A\n    entry/ go()\n'
     '  comment (on A "stop")\n    x\n', [('S19', 5)]),
    ('machine M\n  initial -> A\n  state A\n    E -> A\n'
     '  comment (on A E -> A name "E")\n    x\n', [('S20', 5)]),
    ('machine M\n  initial -> A\n  state A\n  comment K\n    x\n'
     '  comment K\n    y\n', [('S21', 6)]),
    ('machine M\n  initial -> A\n  state A\n  comment K (on K)\n    x\n',
     [('S22', 4)]),
    ('machine M\n  initial -> A\n  state A\n  comment (on A\n',
     [('N35', 4)]),
    ('machine M\n  initial -> A\n  state A\n  comment (under A)\n',
     [('N35', 4)]),
    ('machine M\n  initial -> A\n  state A\n  comment (on A, , B)\n',
     [('N35', 4)]),
    ('machine M\n  initial -> A\n  state A\n  comment (on A "")\n',
     [('N35', 4)]),
    ('machine M\n  initial -> A\n  choice C\n    comment\n    [x] -> A\n'
     '    [else] -> A\n  state A\n', [('N12', 4)]),
    ('comment\n  x\nmachine M\n  initial -> A\n  state A\n', [('N02', 1)]),
    ('machine M\n  initial -> A\n  state A\n  comment K (was L)\n',
     [('U01', 4)]),
    ('machine M\n  initial -> A\n  state A\n  comment _comment1\n',
     [('U02', 4)]),
])
def test_issues(text, expected):
    assert issues(text) == expected


def test_comment_event_is_a_transition():
    tree = N.parse('machine M\n  initial -> A\n  state A\n    comment -> B\n'
                   '  state B\n')
    assert N.analyze(tree) == []
    assert [t.event for t in tree.machines[0].children[1].transitions] == \
        ['comment']


def test_build(tmp_path):
    tree = N.parse(DOORS)
    N.analyze(tree)
    text = B.encode(B.build(tree))
    B.verify(text)
    found = comments_of(text)
    names = {v[0]: v for v in found.values()}
    ids = {v[0]: k for k, v in states(text).items()}
    assert names['Floors'][2] == [(ids['Idle'], N.SUBJECT_ELEMENT, ''),
                                  (ids['Moving'], N.SUBJECT_ELEMENT, '')]
    doors = names['']
    assert [link[1:] for link in doors[2]] == [
        (N.SUBJECT_ELEMENT, ''), (N.SUBJECT_BODY, 'open_doors()'),
        (N.SUBJECT_NAME, 'Id'), (N.SUBJECT_ELEMENT, '')]
    assert doors[2][0][0] == '{}-{}'.format(ids['DoorsOpen'], ids['Idle'])
    document = CyberiadaML.Document()
    document.decode(text)
    machine = document.get_state_machines()[0]
    for comment in machine.find_elements_by_types(
            [CyberiadaML.elementComment]):
        # the comment of the simple state Idle goes to the machine
        assert comment.get_parent().get_id() == machine.get_id()
        assert comment.get_markup() == B.MARKDOWN
        assert comment.has_geometry()
    path = tmp_path / 'comments.graphml'
    path.write_text(text, encoding='utf-8')
    assert validate(str(path)) in (None, [])


def test_comment_in_a_composite_stays():
    tree = N.parse('machine M\n  initial -> A\n  state A\n    initial -> X\n'
                   '    comment K (on X)\n      inside\n    state X\n')
    N.analyze(tree)
    document = CyberiadaML.Document()
    document.decode(B.encode(B.build(tree)))
    comment = document.get_state_machines()[0].find_elements_by_types(
        [CyberiadaML.elementComment])[0]
    assert comment.get_parent().get_name() == 'A'
    assert '    comment K (on X)\n      inside\n' in \
        N.render(R.read(document))


def editor_drawn():
    """A drawn document with what an editor makes: a fragment link to a
    transition, a link to the initial, a formal comment, a title the
    notation cannot write, two comments with one title."""
    original = drawn('machine M\n  initial -> A\n  state A\n'
                     '    GO [ready] -> B / start()\n  state B\n'
                     '    entry/ run()\n    STOP -> A\n')
    document = CyberiadaML.Document()
    document.decode(original)
    machine = document.get_state_machines()[0]
    by_name = {e.get_name(): e for e in machine.find_elements_by_types(
        [CyberiadaML.elementSimpleState])}
    initial = machine.find_elements_by_types([CyberiadaML.elementInitial])[0]
    go = [t for t in machine.get_transitions()
          if t.get_source_element_id() == by_name['A'].get_id()][0]
    first = document.new_comment(machine, 'Plan', 'the plan')
    document.add_comment_to_element_body(first, go, 'start()')
    document.add_comment_to_element(first, initial)
    document.new_comment(machine, 'say "hi"', 'quoted title')
    document.new_comment(machine, 'Twin', 'one')
    document.new_comment(machine, 'Twin', 'two')
    document.new_formal_comment(machine, 'CGML_COMPONENT timer', 'type/ Timer')
    return document.encode()


def test_read_editor_drawn():
    tree = R.read(R.decode(editor_drawn()))
    text = N.render(tree)
    assert '  comment Plan (on A GO [ready] -> B "start()")\n    the plan\n' \
        in text
    assert '  comment _comment1\n    quoted title\n' in text
    assert '  comment _comment2\n    one\n  comment _comment3\n    two\n' \
        in text
    assert '  # note: CGML_COMPONENT timer: type/ Timer\n' in text
    assert N.analyze(N.parse(text), changing=True) == []


def test_update_keeps_what_the_notation_does_not_show():
    original = editor_drawn()
    before = comments_of(original)
    old = M.Original(original)
    new = old.notation.replace('    the plan\n', '    the plan, revised\n')
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C11']
    after = comments_of(conversion.graphml)
    plan = [k for k, v in before.items() if v[0] == 'Plan'][0]
    # the link to the initial, unseen, stays; the titles stay
    assert after[plan][2] == before[plan][2]
    assert after[plan][1] == 'the plan, revised'
    assert sorted(v[0] for v in after.values()) == \
        sorted(v[0] for v in before.values())


def lift():
    tree = N.parse(DOORS)
    N.analyze(tree)
    return B.encode(B.build(tree))


def test_update_add_edit_relink_remove(tmp_path):
    original = lift()
    before = comments_of(original)
    old = M.Original(original)
    new = old.notation \
        .replace('  comment Floors (on Idle, Moving)\n',
                 '  comment Order (was Floors) (on Idle)\n') \
        .replace('Idle name "Id", Floors)', 'Idle name "Id", Order)') \
        .replace('  comment Waiting (on Moving)\n    Written in a simple '
                 'state.\n', '') + \
        '  comment Safety (on DoorsOpen)\n    Never move with open doors.\n'
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert sorted(codes(conversion)) == ['C09', 'C10', 'C11', 'C12']
    after = comments_of(conversion.graphml)
    floors = [k for k, v in before.items() if v[0] == 'Floors'][0]
    assert after[floors][0] == 'Order'
    assert len(after[floors][2]) == 1
    assert [v[0] for v in after.values()].count('Safety') == 1
    assert 'Waiting' not in [v[0] for v in after.values()]
    unnamed = [k for k, v in before.items() if v[0] == ''][0]
    assert after[unnamed] == before[unnamed]
    path = tmp_path / 'changed.graphml'
    path.write_text(conversion.graphml, encoding='utf-8')
    assert validate(str(path)) in (None, [])


def test_update_matches_an_unchanged_text():
    original = lift()
    old = M.Original(original)
    new = old.notation.replace('  comment Waiting (on Moving)\n',
                              '  comment (on Moving)\n')
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C11']
    assert '' in [v[0] for v in comments_of(conversion.graphml).values()]


def test_link_follows_an_edited_transition():
    original = lift()
    before = comments_of(original)
    old = M.Original(original)
    new = old.notation.replace('TIMEOUT -> Idle / close_doors()',
                               'TIMEOUT [empty] -> Idle / close_doors()') \
        .replace('(on DoorsOpen TIMEOUT -> Idle,',
                 '(on DoorsOpen TIMEOUT [empty] -> Idle,')
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C08']
    assert comments_of(conversion.graphml) == before


def test_drawn_comment_grows():
    original = lift()
    old = M.Original(original)
    new = old.notation.replace('    Fewer turns.\n',
                               '    Fewer turns.\n    And less wear.\n'
                               '    And a calm ride.\n')
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors

    def rect(graphml):
        document = CyberiadaML.Document()
        document.decode(graphml)
        document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
        comment = [c for c in document.get_state_machines()[0]
                   .find_elements_by_types([CyberiadaML.elementComment])
                   if c.get_name() == 'Floors'][0]
        r = comment.get_geometry_rect()
        return r.x, r.y, r.width, r.height
    x0, y0, w0, h0 = rect(original)
    x1, y1, w1, h1 = rect(conversion.graphml)
    assert (w1, h1 - h0) == (w0, 2 * 20.0)
    assert abs(x1 - x0) < 1 and abs(y1 - y0) < 1


def test_comment_of_a_removed_container_comes_back():
    original = drawn('machine M\n  initial -> A\n  state A\n    initial -> X\n'
                     '    comment K (on X)\n      inside\n    state X\n'
                     '  state B\n')
    old = M.Original(original)
    new = 'machine M\n  initial -> B\n  state B\n  comment K\n    inside\n'
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert 'C09' in codes(conversion)
    assert [v[:2] for v in comments_of(conversion.graphml).values()] == \
        [('K', 'inside')]


@pytest.mark.parametrize('language', ['en', 'ru'])
def test_change_messages(language):
    texts = L.Texts(language)
    for code in ('C09', 'C10', 'C11', 'C12'):
        assert 'K' in texts.change(Change(code, 'n1', name='K'))
    for code, fields in (('N35', {'text': 't'}),
                         ('R05', {'subject': 's', 'known': 'k'}),
                         ('R06', {'subject': 's', 'count': 2}),
                         ('S19', {'fragment': 'f', 'subject': 's'}),
                         ('S20', {}), ('S21', {'name': 'K', 'first': 1}),
                         ('S22', {'name': 'K'})):
        assert texts.message(N.Issue(code, 1, **fields))


def test_through_the_editor(stub, tmp_path):
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('A lift with one call button on every floor',
                      encoding='utf-8')
    stub.answer(chat_answer(fenced(DOORS)))
    first = tmp_path / 'lift.graphml'
    run = editor(['--run-plugin', 'hsm-maker:draw', '--plugin-param',
                  'prompt=@' + str(prompt)] + model(stub) +
                 ['--save', str(first), '--dump-plugin'], tmp_path, 'k')
    assert run.returncode == 0, run.stdout + run.stderr
    text = first.read_text(encoding='utf-8')
    before = comments_of(text)
    assert sorted(v[0] for v in before.values()) == ['', 'Floors', 'Waiting']
    old = M.Original(text)
    stub.answer(chat_answer(fenced(old.notation.replace(
        '    Written in a simple state.\n', '    Moved to the machine.\n'))))
    request = tmp_path / 'change.txt'
    request.write_text('Correct the comment of Idle', encoding='utf-8')
    result = tmp_path / 'changed.graphml'
    run = editor([str(first), '--run-plugin', 'hsm-maker:change',
                  '--plugin-param', 'change=@' + str(request)] + model(stub) +
                 ['--save', str(result), '--dump-plugin'], tmp_path, 'k')
    assert run.returncode == 0, run.stdout + run.stderr
    assert 'changed the comment Waiting' in run.stdout
    after = comments_of(result.read_text(encoding='utf-8'))
    assert sorted(after) == sorted(before)
    waiting = [k for k, v in before.items() if v[0] == 'Waiting'][0]
    assert after[waiting][1] == 'Moved to the machine.'
