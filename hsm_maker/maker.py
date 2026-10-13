# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The conversion and the draft-check-repair loop
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

"""One notation to a document, and the loop that asks the model until the
document is made: the acceptance is a fact of the checks, never the word of
the model."""

from .builder import BuildError, GEOMETRY_FULL, build, encode, verify
from .client import RequestLimitError, Usage
from .language import AUTO, Texts, choose
from .notation import ERROR, NotationError, WARNING, analyze, extract, parse

ROUNDS = 3
ACCEPTED = 'accepted'
ROUNDS_SPENT = 'rounds'
REQUEST_LIMIT = 'request-limit'


class Conversion:
    """One notation converted."""

    def __init__(self, notation):
        self.notation = notation
        self.diagram = None
        self.document = None
        self.graphml = None
        self.errors = []
        self.warnings = []

    @property
    def ok(self):
        return self.graphml is not None and not self.errors


class Result:
    """The outcome of a run."""

    def __init__(self, conversion, rounds, usage, language, reason):
        self.ok = conversion is not None and conversion.ok
        self.graphml = conversion.graphml if conversion else None
        self.document = conversion.document if conversion else None
        self.notation = conversion.notation if conversion else None
        self.errors = conversion.errors if conversion else []
        self.warnings = conversion.warnings if conversion else []
        self.rounds = rounds
        self.usage = usage
        self.language = language
        self.reason = reason


def convert(notation, geometry=GEOMETRY_FULL):
    """Parse, analyse, build, encode and verify one notation."""
    conversion = Conversion(notation)
    try:
        conversion.diagram = parse(notation)
    except NotationError as error:
        conversion.errors = error.issues
        return conversion
    issues = analyze(conversion.diagram)
    conversion.errors = [i for i in issues if i.severity == ERROR]
    conversion.warnings = [i for i in issues if i.severity == WARNING]
    if conversion.errors:
        return conversion
    try:
        document = build(conversion.diagram, geometry)
        graphml = encode(document)
        verify(graphml)
    except BuildError as error:
        conversion.errors = error.issues
        return conversion
    conversion.document = document
    conversion.graphml = graphml
    return conversion


def feedback(conversion, texts, truncated=False):
    """The message to the model about a rejected conversion."""
    lines = [texts.text('header')]
    if truncated:
        lines.append(texts.text('truncated'))
    lines.extend(texts.render(i) for i in conversion.errors +
                 conversion.warnings)
    lines.append(texts.text('footer'))
    return '\n'.join(lines)


def _spent(client, before):
    return Usage(client.usage.requests - before.requests,
                 client.usage.input_tokens - before.input_tokens,
                 client.usage.output_tokens - before.output_tokens)


def run(prompt, client, language=AUTO, geometry=GEOMETRY_FULL,
        rounds=ROUNDS, log=None):
    """Ask the model until the diagram is made, at most `rounds` times.
    `log(number, reply, conversion)` is called after every round."""
    language = choose(language, prompt)
    texts = Texts(language)
    before = Usage(client.usage.requests, client.usage.input_tokens,
                   client.usage.output_tokens)
    question = {'role': 'user', 'content': prompt}
    messages = [question]
    conversion = None
    reason = ROUNDS_SPENT
    done = 0
    for number in range(1, rounds + 1):
        try:
            reply = client.complete(texts.system, messages)
        except RequestLimitError:
            reason = REQUEST_LIMIT
            break
        done = number
        conversion = convert(extract(reply.text), geometry)
        if log is not None:
            log(number, reply, conversion)
        if conversion.ok:
            reason = ACCEPTED
            break
        # only the last answer stays: a round costs about the first one
        messages = [question,
                    {'role': 'assistant', 'content': reply.text},
                    {'role': 'user',
                     'content': feedback(conversion, texts, reply.truncated)}]
    return Result(conversion, done, _spent(client, before), language, reason)
