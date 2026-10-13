# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the conversion and the repair loop
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

from conftest import FAKE_INPUT, FAKE_OUTPUT, FakeClient, diagram, fenced
import hsm_maker
from hsm_maker import maker as M
from hsm_maker.builder import GEOMETRY_NONE
from hsm_maker.language import Texts

LIFT = diagram('lift.hsm')
WRONG = 'machine M\n  initial -> A\n  state A\n    GO -> Missng\n  state B\n'
PROMPT = 'A lift with one call button on every floor'


def test_accepted_at_once():
    client = FakeClient([fenced(LIFT)])
    result = M.run(PROMPT, client)
    assert (result.ok, result.reason, result.rounds, result.language) == \
        (True, M.ACCEPTED, 1, 'en')
    assert '<data key="dName">Lift</data>' in result.graphml
    assert result.notation == LIFT
    assert (result.usage.requests, result.usage.input_tokens,
            result.usage.output_tokens) == (1, FAKE_INPUT, FAKE_OUTPUT)
    system, messages = client.calls[0]
    assert system == Texts('en').system
    assert messages == [{'role': 'user', 'content': PROMPT}]


def test_repaired():
    rounds = []
    client = FakeClient([fenced(WRONG), fenced(LIFT)])
    result = M.run(PROMPT, client, log=lambda n, r, c: rounds.append(
        (n, c.ok)))
    assert (result.ok, result.rounds) == (True, 2)
    assert rounds == [(1, False), (2, True)]
    messages = client.calls[1][1]
    assert [m['role'] for m in messages] == ['user', 'assistant', 'user']
    assert messages[1]['content'] == fenced(WRONG)
    assert messages[2]['content'] == '\n'.join([
        'The diagram was not accepted:',
        "line 4: unknown target 'Missng'; known: A, B",
        Texts('en').text('footer')])


def test_only_the_last_answer_is_kept():
    client = FakeClient([fenced(WRONG), fenced(WRONG + '#\n'), fenced(LIFT)])
    assert M.run(PROMPT, client).ok
    messages = client.calls[2][1]
    assert len(messages) == 3
    assert messages[1]['content'] == fenced(WRONG + '#\n')


def test_rounds_spent():
    client = FakeClient([fenced(WRONG)] * 2)
    result = M.run(PROMPT, client, rounds=2)
    assert (result.ok, result.reason, result.rounds, result.graphml) == \
        (False, M.ROUNDS_SPENT, 2, None)
    assert [i.code for i in result.errors] == ['R01']


def test_request_limit():
    result = M.run(PROMPT, FakeClient([fenced(WRONG)]))
    assert (result.ok, result.reason, result.rounds) == \
        (False, M.REQUEST_LIMIT, 1)
    assert M.run(PROMPT, FakeClient([])).notation is None


def test_truncated_answer():
    client = FakeClient([(fenced('machine M\n'), True), fenced(LIFT)])
    M.run(PROMPT, client)
    assert Texts('en').text('truncated') in client.calls[1][1][2]['content']


def test_russian():
    client = FakeClient([fenced(WRONG), fenced(LIFT)])
    result = M.run('Лифт с одной кнопкой вызова на каждом этаже', client)
    assert result.language == 'ru'
    assert client.calls[0][0] == Texts('ru').system
    assert "строка 4: неизвестная цель 'Missng'" in client.calls[1][1][2][
        'content']


def test_no_geometry():
    result = M.run(PROMPT, FakeClient([fenced(LIFT)]),
                   geometry=GEOMETRY_NONE)
    assert 'geometry/ none' in result.graphml


def test_answer_without_a_block():
    assert M.run(PROMPT, FakeClient([LIFT])).ok


def test_warnings_do_not_stop():
    result = M.run(PROMPT, FakeClient([fenced(LIFT + '  state Spare\n')]))
    assert result.ok
    assert [i.code for i in result.warnings] == ['W01']


def test_convert_stages():
    assert [i.code for i in M.convert('state A\n').errors] == ['N02']
    assert [i.code for i in M.convert(WRONG).errors] == ['R01']
    good = M.convert(LIFT)
    assert good.ok and good.document is not None
    assert good.diagram.machines[0].name == 'Lift'


def test_feedback_lists_warnings_too():
    conversion = M.convert(WRONG)
    conversion.warnings = M.convert(LIFT + '  state Spare\n').warnings
    text = M.feedback(conversion, Texts('en'))
    assert "warning: line 26: 'Spare' is unreachable" in text


def test_make():
    result = hsm_maker.make(PROMPT, FakeClient([fenced(LIFT)]),
                            language='en')
    assert result.ok and result.language == 'en'
