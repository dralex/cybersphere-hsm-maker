# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the messages of a run
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

import io
import re

import pytest

from conftest import FAKE_INPUT, FAKE_OUTPUT, PNG, FakeClient, diagram, fenced
from hsm_maker import client as C
from hsm_maker import maker as M
from hsm_maker import report as R
from hsm_maker.language import Texts, languages
from hsm_maker.notation import WARNING, Issue
from hsm_maker.reader import ReadError

LIFT = diagram('lift.hsm')
WRONG = 'machine M\n  initial -> A\n  state A\n    GO -> Missng\n  state B\n'
EN = Texts('en')
IMAGE = C.Image(PNG, C.PNG, 'lift.png')


def run(answers, verbosity=0, pictures=(), rounds=M.ROUNDS):
    """A run with the report: the result, the messages, the errors."""
    messages, errors = io.StringIO(), io.StringIO()
    report = R.Report(EN, messages, verbosity, 'model-1', rounds, errors)
    result = M.run('a lift', FakeClient(answers), rounds=rounds,
                   log=report.log, trace=report.trace, pictures=pictures)
    report.summary(result)
    return result, messages.getvalue(), errors.getvalue()


def hint(key, texts=EN):
    return texts.text('hint', text=texts.text(key))


def test_progress():
    result, messages, errors = run([fenced(WRONG), fenced(LIFT)])
    assert result.ok and errors == ''
    lines = messages.splitlines()
    assert lines[0] == 'round 1 of 3: asking model-1...'
    assert lines[1].startswith(
        'round 1: the answer has issues (1), the model is asked to correct '
        'them ({} / {} tokens, '.format(FAKE_INPUT, FAKE_OUTPUT))
    assert lines[2] == 'round 2 of 3: asking model-1...'
    assert lines[3].startswith('round 2: the diagram is accepted (')
    assert lines[4] == 'rounds: 2, requests: 2, input tokens: {}, output ' \
        'tokens: {}'.format(2 * FAKE_INPUT, 2 * FAKE_OUTPUT)
    assert '-- ' not in messages


def test_dialog():
    _, messages, _ = run([fenced(WRONG), fenced(LIFT)], R.DIALOG, [IMAGE])
    assert messages.count('-- system: ') == 1
    assert '-- system: the instructions in en, {} characters; -vv shows ' \
        'them\n'.format(len(EN.system)) in messages
    assert EN.system.strip() not in messages
    assert '-- user:\n{}\n[picture lift.png, image/png, 1 KiB]\n'.format(
        EN.text('picture_request', comment='a lift')) in messages
    assert re.search(r'-- assistant \(\d+ s, {} / {} tokens\):\n'.format(
        FAKE_INPUT, FAKE_OUTPUT) + re.escape(fenced(WRONG)), messages)
    assert '-- issues:\nline 4 "GO -> Missng": unknown target \'Missng\'; ' \
        'known: A, B\n' in messages
    assert '-- with the request of round 1 and the last answer\n-- user:\n' \
        'The diagram was not accepted:' in messages
    assert IMAGE.base64() not in messages


def test_system_prompt():
    _, messages, _ = run([fenced(LIFT)], R.SYSTEM)
    assert EN.system.strip() in messages
    assert '-vv shows them' not in messages


def test_not_made():
    result, messages, errors = run([fenced(WRONG)], rounds=1)
    assert not result.ok
    assert 'round 1: the answer has issues (1), no rounds left (' in messages
    assert 'rounds: 1, requests: 1' in messages
    lines = errors.splitlines()
    assert lines[0] == 'The diagram is not made: the answer of round 1 ' \
        'still has issues (1):'
    assert lines[1:] == ['  line 4 "GO -> Missng": unknown target '
                         '\'Missng\'; known: A, B', hint('hint_rounds')]


def test_cut():
    _, messages, errors = run([(fenced(WRONG), True)], R.DIALOG, rounds=1)
    assert 'round 1: the answer was cut by the length limit' in messages
    assert ', cut by the length limit):' in messages
    assert errors.splitlines()[-1] == hint('hint_truncated')


def test_no_picture():
    _, messages, errors = run(['NO PICTURE'], R.DIALOG, [IMAGE])
    assert 'round 1: the model does not see the picture (' in messages
    assert errors.splitlines() == [EN.text('not_made_picture'),
                                   hint('hint_no_picture')]


def test_request_limit():
    _, messages, errors = run([])
    assert messages.startswith('round 1 of 3: asking model-1...')
    assert errors.splitlines() == [EN.text('not_made_limit'),
                                   hint('hint_request_limit')]


def test_quoted():
    notation = 'machine M\n  state ' + 'X' * 100 + '\n'
    text = R.quoted(EN, Issue('S05', 2, name='M'), notation)
    assert text.startswith('line 2 "state XXX')
    assert text.endswith('...": machine \'M\' is empty')
    assert len(text.split('"')[1]) == R.QUOTE_LIMIT
    assert R.quoted(EN, Issue('W01', 1, WARNING, name='M'), notation) == \
        'warning: line 1 "machine M": \'M\' is unreachable'
    assert R.quoted(EN, Issue('N04'), notation) == 'the diagram has no machine'
    assert R.quoted(EN, Issue('S05', 9, name='M'), notation) == \
        "line 9: machine 'M' is empty"


@pytest.mark.parametrize('error, key', [
    (C.ConfigError('no key', C.KEY_HINT), 'hint_key'),
    (C.ConfigError('bad option'), None),
    (C.RequestLimitError('limit'), 'hint_request_limit'),
    (C.ClientError('x', 400), 'hint_refused'),
    (C.ClientError('x', 401), 'hint_key_refused'),
    (C.ClientError('x', 402), 'hint_balance'),
    (C.ClientError('x', 403), 'hint_key_refused'),
    (C.ClientError('x', 404), 'hint_not_found'),
    (C.ClientError('x', 413), 'hint_too_large'),
    (C.ClientError('x', 422), 'hint_refused'),
    (C.ClientError('x', 429), 'hint_busy'),
    (C.ClientError('x', 503), 'hint_server'),
    (C.ClientError('x', 529), 'hint_server'),
    (C.ClientError('x', 418), None),
    (C.ClientError('x', kind=C.NETWORK), 'hint_network'),
    (C.ClientError('x', kind=C.TIMED_OUT), 'hint_timeout'),
    (C.ClientError('x', kind=C.ANSWER), 'hint_answer'),
    (ReadError('several regions'), 'hint_read'),
    (OSError('no file'), None)])
def test_hint(error, key):
    for language in languages():
        texts = Texts(language)
        assert R.hint(texts, error) == (hint(key, texts) if key else None)


def test_explain():
    errors = io.StringIO()
    ru = Texts('ru')
    R.Report(ru, io.StringIO(), errors=errors).explain(
        C.ClientError('HTTP 402 from x: Insufficient Balance', 402))
    assert errors.getvalue().splitlines() == [
        'hsm-maker: HTTP 402 from x: Insufficient Balance',
        hint('hint_balance', ru)]
