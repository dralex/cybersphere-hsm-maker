# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the patch of a document by a changed notation
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

import CyberiadaML
from conftest import diagram, validate
from hsm_maker import builder as B
from hsm_maker import maker as M
from hsm_maker import notation as N

STATES = [CyberiadaML.elementSimpleState, CyberiadaML.elementCompositeState]


def drawn(text):
    """A drawn document of a notation, as a person would have it."""
    tree = N.parse(text)
    assert [i for i in N.analyze(tree) if i.severity == N.ERROR] == []
    return B.encode(B.build(tree))


def states(graphml):
    """The states by id: name and absolute rect (the Qt coordinates follow
    the machine centre, which moves when the machine grows)."""
    document = CyberiadaML.Document()
    document.decode(graphml)
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    found = {}
    for machine in document.get_state_machines():
        for element in machine.find_elements_by_types(STATES):
            r = element.get_geometry_rect()
            found[element.get_id()] = (element.get_name(), r.x, r.y,
                                       r.width, r.height)
    return found


def codes(conversion):
    return [c.code for c in conversion.changes]


LIFT = drawn(diagram('lift.hsm'))


def test_unchanged():
    old = M.Original(LIFT)
    conversion = M.change(LIFT, old.notation, old=old)
    assert conversion.ok and not conversion.changes
    assert states(conversion.graphml) == states(LIFT)


def test_rename_add_and_action():
    old = M.Original(LIFT)
    new = old.notation.replace('  state Idle\n', '  state Waiting (was Idle)\n') \
        .replace('-> Idle', '-> Waiting') \
        .replace('    CALL [call_floor == floor] -> DoorsOpen\n',
                 '    CALL [call_floor == floor] -> DoorsOpen\n'
                 '    SERVICE -> Maintenance\n') \
        .replace('close_doors()', 'close_doors(); beep()') + \
        '  state Maintenance\n    entry/ lock_doors()\n    SERVICE_DONE -> Waiting\n'
    conversion = M.change(LIFT, new, old=old)
    assert conversion.ok, conversion.errors
    assert sorted(codes(conversion)) == ['C01', 'C03', 'C06', 'C06', 'C08']
    before, after = states(LIFT), states(conversion.graphml)
    assert {i: after[i][1:] for i in before} == \
        {i: value[1:] for i, value in before.items()}
    assert after['n1'][0] == 'Waiting'
    added = [i for i in after if i not in before]
    assert [after[i][0] for i in added] == ['Maintenance']
    B.verify(conversion.graphml)


def test_remove_with_transitions_and_comment_links(tmp_path):
    document = CyberiadaML.Document()
    document.decode(LIFT)
    machine = document.get_state_machines()[0]
    doors = [e for e in machine.find_elements_by_types(STATES)
             if e.get_name() == 'DoorsOpen'][0]
    comment = document.new_comment(machine, 'the doors')
    document.add_comment_to_element(comment, doors)
    original = document.encode()
    old = M.Original(original)
    new = old.notation.replace('    CALL [call_floor == floor] -> DoorsOpen\n', '') \
        .replace('    FLOOR [floor == target] -> DoorsOpen\n',
                 '    FLOOR [floor == target] -> Idle\n')
    new = new[:new.index('  state DoorsOpen')]
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert sorted(codes(conversion)) == ['C02', 'C06', 'C07', 'C07', 'C07']
    result = CyberiadaML.Document()
    result.decode(conversion.graphml, strict=True)
    comments = result.get_state_machines()[0].find_elements_by_types(
        [CyberiadaML.elementComment])
    assert [c.get_body() for c in comments] == ['the doors']
    assert len(comments[0].get_subjects()) == 0
    path = tmp_path / 'removed.graphml'
    path.write_text(conversion.graphml, encoding='utf-8')
    assert validate(str(path)) in (None, [])


def test_move_keeps_the_id_and_the_comment():
    original = drawn('machine M\n  initial -> A\n  state A\n    initial -> X\n'
                     '    state X\n    GO -> B\n  state B\n    initial -> Y\n'
                     '    state Y\n')
    document = CyberiadaML.Document()
    document.decode(original)
    machine = document.get_state_machines()[0]
    x = [e for e in machine.find_elements_by_types(STATES)
         if e.get_name() == 'X'][0]
    comment = document.new_comment(machine, 'about x')
    document.add_comment_to_element(comment, x)
    x_id = x.get_id()
    original = document.encode()
    old = M.Original(original)
    new = 'machine M\n  initial -> A\n  state A\n    initial -> Z\n' \
        '    state Z\n    GO -> B\n  state B\n    initial -> Y\n    state Y\n' \
        '    state X (was A::X)\n'
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert 'C04' in codes(conversion)
    result = CyberiadaML.Document()
    result.decode(conversion.graphml, strict=True)
    moved = result.find_element_by_id(x_id)
    assert moved.get_qualified_name() == 'B::X'
    assert moved.has_geometry()
    comment = result.get_state_machines()[0].find_elements_by_types(
        [CyberiadaML.elementComment])[0]
    assert [s.get_element().get_id() for s in comment.get_subjects()] == \
        [x_id]


def test_state_actions():
    original = drawn('machine M\n  initial -> A\n  state A\n    entry/ go()\n'
                     '    TICK / count()\n')
    old = M.Original(original)
    new = old.notation.replace('    TICK / count()\n',
                               '    TICK propagate / count()\n    LATER / defer\n')
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C05']
    result = CyberiadaML.Document()
    result.decode(conversion.graphml, strict=True)
    a = result.get_state_machines()[0].find_elements_by_types(STATES)[0]
    assert [(x.get_trigger(), x.get_propagation(), x.get_behavior())
            for x in a.get_actions()][1:] == [
        ('TICK', CyberiadaML.eventPropagationPropagate, 'count()'),
        ('LATER', CyberiadaML.eventPropagationDefer, '')]


def test_notation_normal_form_keeps_the_original_text():
    document = CyberiadaML.Document()
    machine = document.new_state_machine('M')
    init = document.new_initial(machine)
    a = document.new_state(machine, 'A')
    a.add_action(CyberiadaML.Action(CyberiadaML.actionEntry,
                                    'start()\n# the comment of the code\nrun()'))
    document.new_transition(machine, CyberiadaML.transitionExternal, init, a,
                            CyberiadaML.Action())
    original = document.encode()
    old = M.Original(original)
    conversion = M.change(original, old.notation + '  state B\n', old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C01']
    assert 'the comment of the code' in conversion.graphml


def test_unnamed_stays_unnamed():
    document = CyberiadaML.Document()
    machine = document.new_state_machine('M')
    init = document.new_initial(machine)
    a = document.new_state(machine, 'A')
    final = document.new_final(machine)
    document.new_transition(machine, CyberiadaML.transitionExternal, init, a,
                            CyberiadaML.Action())
    document.new_transition(machine, CyberiadaML.transitionExternal, a, final,
                            CyberiadaML.Action('STOP'))
    original = document.encode()
    old = M.Original(original)
    assert 'final _final1' in old.notation
    conversion = M.change(original, old.notation.replace(
        'STOP -> _final1', 'STOP -> _final1 / bye()'), old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C08']
    result = CyberiadaML.Document()
    result.decode(conversion.graphml)
    finals = result.get_state_machines()[0].find_elements_by_types(
        [CyberiadaML.elementFinal])
    assert [f.get_name() for f in finals] == ['']


def test_kind_change_and_machines():
    original = drawn('machine M\n  initial -> A\n  state A\n    GO -> C\n'
                     '  state C\nmachine Old\n  initial -> X\n  state X\n')
    old = M.Original(original)
    new = 'machine M\n  initial -> A\n  state A\n    GO -> C\n  final C\n' \
        'machine Fresh\n  initial -> Y\n  state Y\n'
    conversion = M.change(original, new, old=old)
    assert conversion.ok, conversion.errors
    # the machine Old goes with its initial transition
    assert sorted(codes(conversion)) == ['C01', 'C01', 'C01', 'C01', 'C02',
                                         'C02', 'C06', 'C06', 'C07', 'C07']


def test_tolerated_original_issue():
    document = CyberiadaML.Document()
    machine = document.new_state_machine('M')
    document.new_state(machine, 'A')
    original = document.encode()
    old = M.Original(original)
    conversion = M.change(original, old.notation + '  state B\n', old=old)
    assert conversion.ok, conversion.errors
    assert [i.code for i in conversion.warnings] == ['S04']


def test_naming_issues():
    old = M.Original(LIFT)
    cases = [
        (old.notation.replace('  state Idle\n', '  state Waiting (was Nowhere)\n')
         .replace('-> Idle', '-> Waiting'), 'U03'),
        (old.notation.replace('  state DoorsOpen\n',
                              '  state DoorsOpen (was Idle)\n')
         .replace('  state Idle\n', '  state Idle (was Idle)\n'), 'U04'),
        (old.notation + '  state _new\n', 'U02'),
    ]
    for text, code in cases:
        conversion = M.change(LIFT, text, old=old)
        assert not conversion.ok
        assert code in [i.code for i in conversion.errors], (code, conversion.errors)


def test_guard_edited_in_place():
    old = M.Original(LIFT)
    conversion = M.change(LIFT, old.notation.replace(
        'TIMEOUT -> Idle', 'TIMEOUT [doors_free] -> Idle'), old=old)
    assert conversion.ok, conversion.errors
    assert codes(conversion) == ['C08']
    timeout = conversion.changes[0].element

    def route(graphml):
        document = CyberiadaML.Document()
        document.decode(graphml)
        document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
        transition = document.find_element_by_id(timeout)
        source = transition.get_geometry_source_point()
        target = transition.get_geometry_target_point()
        return (transition.get_action().get_guard(), round(source.x),
                round(source.y), round(target.x), round(target.y))
    assert route(conversion.graphml)[1:] == route(LIFT)[1:]
    assert route(conversion.graphml)[0] == 'doors_free'
