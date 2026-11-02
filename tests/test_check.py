# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the check round of a diagram against its picture
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
"""The check round: an accepted diagram compared with its picture once more."""
import io

from conftest import FakeClient, diagram, fenced, png
from hsm_maker import client as C
from hsm_maker import maker as M
from hsm_maker.language import Texts
from hsm_maker.report import Report

LIFT = diagram('lift.hsm')
# the lift with one more state, an accepted correction
CORRECTED = LIFT.replace('  state DoorsOpen',
                         '  state Service\n  state DoorsOpen', 1)
WRONG = 'machine M\n  initial -> A\n  state A\n    GO -> Missing\n'
PICTURE = C.Image(png(640, 480), C.PNG, 'lift.png')


def _run(answers, check=True):
    client = FakeClient(answers)
    return M.run('', client, pictures=[PICTURE], check=check), client


def test_no_changes():
    """NO CHANGES: the diagram stays, the request repeats the first one."""
    result, client = _run([fenced(LIFT), 'NO CHANGES.'])
    assert result.ok and result.check.outcome == M.CHECK_SAME
    assert result.notation == M.convert(LIFT).notation
    assert result.usage.requests == 2
    # the same first message with the picture, the answer, the request
    rounds, check = client.calls[0][1], client.calls[1][1]
    assert check[0] == rounds[0] and check[0]['images']
    assert check[1] == {'role': 'assistant', 'content': fenced(LIFT)}
    assert 'NO CHANGES' in check[2]['content']


def test_corrected():
    """An accepted correction replaces the diagram."""
    result, _ = _run([fenced(LIFT), fenced(CORRECTED)])
    assert result.ok and result.check.outcome == M.CHECK_CHANGED
    assert 'Service' in result.notation and 'Service' in result.graphml
    assert result.answer == fenced(CORRECTED)


def test_rejected_and_failed():
    """A rejected correction, a failed request: the diagram stays."""
    result, _ = _run([fenced(LIFT), fenced(WRONG)])
    assert result.ok and result.check.outcome == M.CHECK_REJECTED
    assert result.check.issues > 0 and 'Service' not in result.notation
    out = io.StringIO()
    Report(Texts('en'), out).summary(result)
    assert 'the correction against the picture was not accepted' in \
        out.getvalue()
    # the request limit: the diagram stays, the reason in the summary
    result, _ = _run([fenced(LIFT)])
    assert result.ok and result.check.outcome is None
    out = io.StringIO()
    Report(Texts('en'), out).summary(result)
    assert 'the check against the picture failed (no more answers)' in \
        out.getvalue()


def test_no_check():
    """Off, or without a picture, no check round."""
    result, client = _run([fenced(LIFT)], check=False)
    assert result.ok and result.check is None and len(client.calls) == 1
    client = FakeClient([fenced(LIFT)])
    result = M.run('a lift', client)
    assert result.ok and result.check is None and len(client.calls) == 1


def test_progress():
    """The progress and the dialog of the check round."""
    out = io.StringIO()
    report = Report(Texts('en'), out, verbosity=1, model='m')
    client = FakeClient([fenced(LIFT), 'NO CHANGES'])
    M.run('', client, pictures=[PICTURE], log=report.log, trace=report.trace)
    text = out.getvalue()
    assert 'check: asking m to compare the diagram with the picture' in text
    assert '== check' in text and 'check: the diagram matches the picture' \
        in text
