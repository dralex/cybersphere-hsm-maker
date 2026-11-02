# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The messages of a run
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

"""The messages of a run: the progress, the dialog with the model, the
failure and the hint what to do. The user never sees the notation, so an
issue quotes its line of the answer."""

import math
import sys
import time

from .client import (ANSWER, NETWORK, TIMED_OUT, ClientError, ConfigError,
                     RequestLimitError)
from .maker import (CHECK, CHECK_CHANGED, CHECK_REJECTED, CHECK_SAME,
                    NO_PICTURE, REQUEST_LIMIT, ROUNDS)
from .notation import WARNING
from .reader import ReadError

PROGRAM = 'hsm-maker'
QUOTE_LIMIT = 60
ELLIPSIS = '...'
KIBIBYTE = 1024
# the verbosity: the dialog, then the system prompt too
DIALOG = 1
SYSTEM = 2
HTTP_HINTS = {400: 'hint_refused', 401: 'hint_key_refused',
              402: 'hint_balance', 403: 'hint_key_refused',
              404: 'hint_not_found', 413: 'hint_too_large',
              422: 'hint_refused', 429: 'hint_busy'}
SERVER_ERRORS = 500
KIND_HINTS = {TIMED_OUT: 'hint_timeout', NETWORK: 'hint_network',
              ANSWER: 'hint_answer'}


def quoted(texts, issue, notation):
    """line N "the line": message; the rendered issue when it has no line
    in the notation."""
    lines = (notation or '').splitlines()
    if issue.line is None or not 1 <= issue.line <= len(lines):
        return texts.render(issue)
    line = lines[issue.line - 1].strip()
    if len(line) > QUOTE_LIMIT:
        line = line[:QUOTE_LIMIT - len(ELLIPSIS)] + ELLIPSIS
    text = texts.text('quote', line=issue.line, text=line,
                      message=texts.text(issue.code, **issue.fields))
    if issue.severity == WARNING:
        text = texts.text('warning', text=text)
    return text


def _hint_key(error):
    key = None
    if isinstance(error, ConfigError):
        key = error.hint
    elif isinstance(error, RequestLimitError):
        key = 'hint_request_limit'
    elif isinstance(error, ClientError):
        key = KIND_HINTS.get(error.kind) or HTTP_HINTS.get(error.status)
        if key is None and error.status is not None and \
                error.status >= SERVER_ERRORS:
            key = 'hint_server'
    elif isinstance(error, ReadError):
        key = 'hint_read'
    return key


def hint(texts, error):
    """What to do about an error; None when there is no hint."""
    key = _hint_key(error)
    return texts.text('hint', text=texts.text(key)) if key else None


class Report:
    """The messages of one run: the progress and the dialog go to `stream`,
    the failure and its hint to `errors`."""

    def __init__(self, texts, stream, verbosity=0, model=None, rounds=ROUNDS,
                 errors=None):
        self.texts = texts
        self.stream = stream
        self.verbosity = verbosity
        self.model = model
        self.rounds = rounds
        self.errors = sys.stderr if errors is None else errors
        self.started = None
        self.system_shown = False

    def _say(self, text, stream=None):
        print(text, file=self.stream if stream is None else stream,
              flush=True)

    def _fail(self, text):
        self._say(text, self.errors)

    def trace(self, number, system, messages):
        """Before a request: the progress, and the messages sent; the number
        None is the placement round, CHECK the check round."""
        self.started = time.monotonic()
        if number is None:
            self._say(self.texts.text('progress_placing', model=self.model))
        elif number == CHECK:
            self._say(self.texts.text('progress_checking', model=self.model))
        else:
            self._say(self.texts.text('progress_ask', number=number,
                                      rounds=self.rounds, model=self.model))
        if self.verbosity < DIALOG:
            return
        if number is None or number == CHECK:
            self._say('== ' + ('placement' if number is None else CHECK))
        else:
            self._say('== round {} of {}'.format(number, self.rounds))
        if not self.system_shown:
            self.system_shown = True
            about = self.texts.text('dialog_system',
                                    language=self.texts.language,
                                    size=len(system))
            if self.verbosity < SYSTEM:
                about += '; ' + self.texts.text('dialog_more')
            self._say('-- system: ' + about)
            if self.verbosity >= SYSTEM:
                self._say(system.rstrip('\n'))
        if number is None or number == CHECK or number > 1:
            # a repair round, the check and the placement repeat the request
            # and the last answer
            self._say('-- ' + self.texts.text('dialog_again'))
            messages = messages[-1:]
        for message in messages:
            self._say('-- {}:'.format(message['role']))
            self._say(message['content'].rstrip('\n'))
            for image in message.get('images') or ():
                self._say(self.texts.text(
                    'dialog_picture', name=image.name or '-',
                    type=image.media_type,
                    size=math.ceil(len(image.data) / KIBIBYTE)))

    def log(self, number, reply, conversion):
        """After an answer: the answer, its issues, the progress; the number
        None is the placement round, its conversion a Placement, CHECK the
        check round, its conversion a Check."""
        seconds = 0 if self.started is None else \
            round(time.monotonic() - self.started)
        spent = {'number': number, 'input': reply.usage.input_tokens,
                 'output': reply.usage.output_tokens, 'seconds': seconds}
        if self.verbosity >= DIALOG:
            about = self.texts.text('dialog_answer', **spent)
            if reply.truncated:
                about += ', ' + self.texts.text('dialog_cut')
            self._say('-- assistant ({}):'.format(about))
            self._say(reply.text.rstrip('\n'))
            if number is not None and number != CHECK and \
                    conversion is not None and \
                    (conversion.errors or conversion.warnings):
                self._say('-- issues:')
                for issue in conversion.errors + conversion.warnings:
                    self._say(quoted(self.texts, issue, conversion.notation))
        if number is None:
            if conversion.error is None:
                self._say(self.texts.text('progress_placed',
                                          placed=conversion.placed,
                                          total=conversion.total, **spent))
            return
        if number == CHECK:
            key = {CHECK_SAME: 'progress_checked_same',
                   CHECK_CHANGED: 'progress_checked_changed',
                   CHECK_REJECTED: 'progress_checked_rejected'}.get(
                       conversion.outcome)
            if key is not None:
                self._say(self.texts.text(key, **spent))
            return
        if conversion is None:
            key = 'progress_blind'
        elif conversion.ok:
            key = 'progress_accepted'
        elif number >= self.rounds:
            key = 'progress_issues_last'
        else:
            key = 'progress_issues'
        count = len(conversion.errors) if conversion is not None else 0
        self._say(self.texts.text(key, count=count, **spent))
        if reply.truncated:
            self._say(self.texts.text('progress_cut', number=number))

    def summary(self, result):
        """The end of a run: the warnings and the usage; for a diagram not
        made the issues quoted, the reason and its hint last."""
        if result.ok:
            for issue in result.warnings:
                self._say(quoted(self.texts, issue, result.notation))
            checked = getattr(result, 'check', None)
            if checked is not None and checked.outcome == CHECK_REJECTED:
                self._say(self.texts.text('warning', text=self.texts.text(
                    'check_rejected', count=checked.issues)))
            elif checked is not None and checked.error is not None:
                self._say(self.texts.text('warning', text=self.texts.text(
                    'check_failed', reason=checked.error)))
            placed = getattr(result, 'placement', None)
            if placed is not None and placed.error is not None:
                self._say(self.texts.text('warning', text=self.texts.text(
                    'placement_failed', reason=placed.error)))
        self._say('rounds: {}, {}'.format(result.rounds, result.usage))
        if result.ok:
            return
        if result.reason == NO_PICTURE:
            self._fail(self.texts.text('not_made_picture'))
            key = 'hint_no_picture'
        elif result.reason == REQUEST_LIMIT:
            self._fail(self.texts.text('not_made_limit'))
            key = 'hint_request_limit'
        else:
            self._fail(self.texts.text('not_made', number=result.rounds,
                                       count=len(result.errors)))
            for issue in result.errors + result.warnings:
                self._fail('  ' + quoted(self.texts, issue, result.notation))
            key = 'hint_truncated' if result.truncated else 'hint_rounds'
        self._fail(self.texts.text('hint', text=self.texts.text(key)))

    def explain(self, error):
        """An error and what to do about it."""
        self._fail('{}: {}'.format(PROGRAM, error))
        text = hint(self.texts, error)
        if text:
            self._fail(text)
