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

from . import placement
from .builder import (BINDING_ERRORS, BuildError, GEOMETRY_FULL,
                      GEOMETRY_UPDATE, ROUTING_ORTHOGONAL, build, encode,
                      verify)
from .client import (ClientError, Image, RequestLimitError, Usage, image_size,
                     load_picture)
from .language import AUTO, Texts, choose
from .notation import (ERROR, NotationError, WARNING, analyze, extract,
                       language_spelling, parse, render)
from .patcher import PatchError, patch
from .reader import decode, read

ROUNDS = 3
ACCEPTED = 'accepted'
ROUNDS_SPENT = 'rounds'
REQUEST_LIMIT = 'request-limit'
NO_PICTURE = 'no-picture'
# a failed placement keeps the full layout
PLACEMENT_ERRORS = (placement.PlacementError, ClientError, BuildError,
                    NotationError) + BINDING_ERRORS
# the answer of a model that does not see the picture
NO_PICTURE_ANSWER = 'NO PICTURE'


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

    def __init__(self, conversion, rounds, usage, language, reason,
                 truncated=False, answer=None):
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
        self.truncated = truncated
        self.answer = answer
        self.placement = None


def _chosen(code_language):
    """The code language a run writes; None when the model declares it."""
    if not code_language or code_language == AUTO:
        return None
    return language_spelling(code_language)


def convert(notation, geometry=GEOMETRY_FULL, code_language=AUTO,
            routing=ROUTING_ORTHOGONAL):
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
        document = build(conversion.diagram, geometry, routing)
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
           code_language=AUTO, routing=ROUTING_ORTHOGONAL):
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
                                  geometry, routing)
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


def _images_of(pictures):
    """The pictures as Image objects: Image objects or file paths."""
    return [picture if isinstance(picture, Image) else load_picture(picture)
            for picture in pictures or ()]


def _blind(reply):
    """Whether the model answered that it does not see the picture."""
    return extract(reply.text).strip().rstrip('.').upper() == \
        NO_PICTURE_ANSWER


def run(prompt, client, language=AUTO, geometry=GEOMETRY_FULL,
        rounds=ROUNDS, log=None, code_language=AUTO, pictures=(), trace=None,
        size=placement.SIZE_FIT, routing=ROUTING_ORTHOGONAL):
    """Ask the model until the diagram is made, at most `rounds` times.
    `trace(number, system, messages)` is called before every request,
    `log(number, reply, conversion)` after every answer; the prompt is the
    comment to the pictures when there are any. The geometry 'picture'
    arranges the diagram as the first picture by the placement round."""
    images = _images_of(pictures)
    before = Usage(client.usage.requests, client.usage.input_tokens,
                   client.usage.output_tokens)
    texts = Texts(choose(language, prompt))
    question = prompt
    if images:
        question = texts.text('picture_request', comment=prompt.strip()) \
            if prompt.strip() else texts.text('picture_alone')
    asked = _asked(question, texts, code_language)
    placing = geometry == placement.GEOMETRY_PICTURE
    if placing:
        geometry = GEOMETRY_FULL
    result = _loop(asked,
                   lambda notation: convert(notation, geometry, code_language,
                                            routing),
                   client, texts, rounds, log, images, trace)
    if placing and images and result.ok:
        _place(result, asked, images, client, texts, code_language, size,
               log, trace, routing)
        result.usage = _spent(client, before)
    return result


def _place(result, asked, images, client, texts, code_language, size, log,
           trace, routing=ROUTING_ORTHOGONAL):
    """The placement round: the accepted diagram arranged as the first
    picture; any failure keeps the full layout with its reason."""
    listed = []
    reply = None
    try:
        dimensions = image_size(images[0].data)
        if dimensions is None:
            raise placement.PlacementError('the size of the picture cannot '
                                           'be read')
        listed = placement.items(result.document, texts)
        edges = placement.transitions(result.document, texts, listed)
        # the first message as in the rounds: the server's cache holds it
        messages = [{'role': 'user', 'content': asked, 'images': list(images)},
                    {'role': 'assistant', 'content': result.answer},
                    {'role': 'user',
                     'content': placement.request(texts, listed,
                                                  *dimensions, edges)}]
        if trace is not None:
            trace(None, texts.system, messages)
        reply = client.complete(texts.system, messages)
        boxes = placement.parse(reply.text, listed, *dimensions)
        sides = placement.parse_sides(reply.text, edges)
        diagram = parse(result.notation)
        diagram.language = _chosen(code_language) or diagram.language
        analyze(diagram)
        result.document, result.graphml = placement.apply(
            diagram, result.graphml, boxes, listed, size, routing, sides,
            edges)
        result.placement = placement.Placement(len(boxes), len(listed))
    except PLACEMENT_ERRORS as error:
        result.placement = placement.Placement(
            0, len(listed), str(error) or type(error).__name__)
    if reply is not None and log is not None:
        log(None, reply, result.placement)


def run_update(graphml, prompt, client, language=AUTO,
               geometry=GEOMETRY_UPDATE, rounds=ROUNDS, log=None,
               code_language=AUTO, pictures=(), trace=None,
               routing=ROUTING_ORTHOGONAL):
    """Ask the model to change the diagram until the change applies, at
    most `rounds` times. Raise ReadError before the first request."""
    images = _images_of(pictures)
    texts = Texts(choose(language, prompt))
    old = Original(graphml)
    request = prompt
    if images:
        request = '\n\n'.join(part for part in (
            prompt.strip(), texts.text('picture_change')) if part)
    question = texts.text('update_request', diagram=old.notation,
                          change=request)
    return _loop(_asked(question, texts, code_language),
                 lambda notation: change(graphml, notation, geometry, old,
                                         code_language, routing),
                 client, texts, rounds, log, images, trace)


def _loop(prompt, conversion_of, client, texts, rounds, log, images=(),
          trace=None):
    """The rounds: ask, convert the answer, give the issues back."""
    before = Usage(client.usage.requests, client.usage.input_tokens,
                   client.usage.output_tokens)
    question = {'role': 'user', 'content': prompt}
    if images:
        # every round shows the picture: the repair checks against it
        question['images'] = list(images)
    messages = [question]
    conversion = None
    reason = ROUNDS_SPENT
    done = 0
    truncated = False
    answer = None
    for number in range(1, rounds + 1):
        if trace is not None:
            trace(number, texts.system, messages)
        try:
            reply = client.complete(texts.system, messages)
        except RequestLimitError:
            reason = REQUEST_LIMIT
            break
        done = number
        truncated = reply.truncated
        answer = reply.text
        if images and _blind(reply):
            reason = NO_PICTURE
            if log is not None:
                log(number, reply, None)
            break
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
                  reason, truncated, answer)
