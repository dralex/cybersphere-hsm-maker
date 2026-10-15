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

from .builder import (BuildError, GEOMETRY_FULL, GEOMETRY_UPDATE, build,
                      encode, verify)
from .client import RequestLimitError, Usage
from .language import AUTO, Texts, choose
from .notation import (ERROR, NotationError, WARNING, analyze, extract,
                       language_spelling, parse, render)
from .patcher import PatchError, patch
from .reader import decode, read

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
        self.changes = []

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
        self.changes = conversion.changes if conversion else []
        self.rounds = rounds
        self.usage = usage
        self.language = language
        self.reason = reason


def _chosen(code_language):
    """The code language a run writes; None when the model declares it."""
    if not code_language or code_language == AUTO:
        return None
    return language_spelling(code_language)


def convert(notation, geometry=GEOMETRY_FULL, code_language=AUTO):
    """Parse, analyse, build, encode and verify one notation."""
    conversion = Conversion(notation)
    try:
        conversion.diagram = parse(notation)
    except NotationError as error:
        conversion.errors = error.issues
        return conversion
    conversion.diagram.language = _chosen(code_language) or \
        conversion.diagram.language
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


class Original:
    """A diagram to be changed: its text, its tree, its notation and the
    issues it already has."""

    def __init__(self, graphml):
        self.graphml = graphml
        self.tree = read(decode(graphml))
        self.notation = render(self.tree)
        self.issues = {i.key for i in analyze(parse(self.notation), True)}


def change(graphml, notation, geometry=GEOMETRY_UPDATE, old=None,
           code_language=AUTO):
    """Apply one changed notation to the diagram of the GraphML text; the
    issues the original already has are warnings. Raise ReadError."""
    old = old if old is not None else Original(graphml)
    conversion = Conversion(notation)
    try:
        conversion.diagram = parse(notation)
    except NotationError as error:
        conversion.errors = error.issues
        return conversion
    conversion.diagram.language = _chosen(code_language) or \
        conversion.diagram.language
    for issue in analyze(conversion.diagram, True):
        if issue.severity == ERROR and issue.key in old.issues:
            issue.severity = WARNING
        if issue.severity == ERROR:
            conversion.errors.append(issue)
        else:
            conversion.warnings.append(issue)
    if conversion.errors:
        return conversion
    try:
        document, changes = patch(graphml, old.tree, conversion.diagram,
                                  geometry)
        text = encode(document)
        verify(text)
    except (PatchError, BuildError) as error:
        conversion.errors = error.issues
        return conversion
    conversion.document = document
    conversion.graphml = text
    conversion.changes = changes
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


def _asked(question, texts, code_language):
    """The question with the code language the model is told to use."""
    chosen = _chosen(code_language)
    if chosen is None:
        return question
    return question + '\n\n' + texts.text('code_language', language=chosen)


def run(prompt, client, language=AUTO, geometry=GEOMETRY_FULL,
        rounds=ROUNDS, log=None, code_language=AUTO):
    """Ask the model until the diagram is made, at most `rounds` times.
    `log(number, reply, conversion)` is called after every round."""
    texts = Texts(choose(language, prompt))
    return _loop(_asked(prompt, texts, code_language),
                 lambda notation: convert(notation, geometry, code_language),
                 client, texts, rounds, log)


def run_update(graphml, prompt, client, language=AUTO,
               geometry=GEOMETRY_UPDATE, rounds=ROUNDS, log=None,
               code_language=AUTO):
    """Ask the model to change the diagram until the change applies, at
    most `rounds` times. Raise ReadError before the first request."""
    texts = Texts(choose(language, prompt))
    old = Original(graphml)
    question = texts.text('update_request', diagram=old.notation,
                          change=prompt)
    return _loop(_asked(question, texts, code_language),
                 lambda notation: change(graphml, notation, geometry, old,
                                         code_language),
                 client, texts, rounds, log)


def _loop(prompt, conversion_of, client, texts, rounds, log):
    """The rounds: ask, convert the answer, give the issues back."""
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
        conversion = conversion_of(extract(reply.text))
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
    return Result(conversion, done, _spent(client, before), texts.language,
                  reason)
