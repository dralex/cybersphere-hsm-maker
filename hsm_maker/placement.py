# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The placement of a diagram as its picture
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

"""The placement round: where the elements of an accepted diagram are in its
picture. The boxes are the seed of the arrange layout, which keeps their
arrangement - not their coordinates, the model's boxes are rough."""

import json
import math
import re

from .builder import (GEOMETRY_NONE, ROUTING_ORTHOGONAL, build, encode,
                      routing_of, verify)
from .cyberiadaml import CyberiadaML
from .notation import INITIAL, MACHINE, STATE, extract
from .reader import decode, read

GEOMETRY_PICTURE = 'picture'
SIZE_FIT = 'fit'
SIZE_PICTURE = 'picture'
SIZES = (SIZE_FIT, SIZE_PICTURE)
BOX = 4
# the smallest side of a box in the picture's pixels
MIN_BOX = 1.0
# picture: the share of the states whose texts fit their scaled boxes
FIT_SHARE = 0.75
OBJECT_RE = re.compile(r'\{.*\}', re.S)


class PlacementError(Exception):
    """The placement round gives no seed."""


class Item:
    """An element of the request."""

    def __init__(self, number, element_id, kind, mark, text):
        self.number = number
        self.element_id = element_id
        self.kind = kind
        self.mark = mark        # placed by its centre: a pseudostate, a point
        self.text = text


class Placement:
    """The outcome of the placement round."""

    def __init__(self, placed, total, error=None):
        self.placed = placed
        self.total = total
        self.error = error


def _is_mark(document, element_id):
    element = document.find_element_by_id(element_id)
    return element is not None and not hasattr(element, 'get_geometry_rect')


def items(document, texts):
    """The numbered elements of a document: the machines, the vertices in
    the notation order, the comments."""
    tree = read(document)
    result = []
    for vertex in tree.walk():
        number = len(result) + 1
        if vertex.kind == MACHINE:
            text = texts.text('placement_frame', number=number,
                              name=vertex.name)
        elif vertex.kind == INITIAL:
            parent = vertex.parent
            text = texts.text('placement_initial', number=number,
                              container=parent.name if parent.kind == MACHINE
                              else parent.path)
        else:
            text = texts.text('placement_vertex', number=number,
                              kind=vertex.kind, path=vertex.path)
        result.append(Item(number, vertex.element_id, vertex.kind,
                           _is_mark(document, vertex.element_id), text))
    for comment in tree.comments():
        number = len(result) + 1
        result.append(Item(number, comment.element_id, 'comment', False,
                           texts.text('placement_comment', number=number,
                                      name=comment.name or comment.title)))
    return result


def request(texts, listed, width, height):
    """The text of the placement request."""
    return texts.text('placement_request', width=width, height=height,
                      elements='\n'.join(item.text for item in listed))


def _object(answer):
    text = extract(answer)
    try:
        return json.loads(text)
    except ValueError:
        match = OBJECT_RE.search(text)
        if match is None:
            raise PlacementError('no JSON object in the answer') from None
        try:
            return json.loads(match.group(0))
        except ValueError:
            raise PlacementError('the JSON object of the answer cannot be '
                                 'read') from None


def _clamp(value, limit):
    return min(max(value, 0.0), float(limit))


def parse(answer, listed, width, height):
    """The boxes {number: (left, top, right, bottom)} of an answer, clamped
    to the picture; unknown numbers and bad boxes are dropped."""
    data = _object(answer)
    if not isinstance(data, dict):
        raise PlacementError('the answer is not a JSON object')
    numbers = {str(item.number): item for item in listed}
    boxes = {}
    for key, value in data.items():
        item = numbers.get(str(key).strip())
        if item is None or not isinstance(value, (list, tuple)) or \
                len(value) != BOX:
            continue
        try:
            coords = [float(c) for c in value]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(c) for c in coords):
            continue
        left, right = sorted((_clamp(coords[0], width),
                              _clamp(coords[2], width)))
        top, bottom = sorted((_clamp(coords[1], height),
                              _clamp(coords[3], height)))
        if not item.mark and (right - left < MIN_BOX or
                              bottom - top < MIN_BOX):
            continue
        boxes[item.number] = (left, top, right, bottom)
    if not boxes:
        raise PlacementError('no box of a listed element in the answer')
    return boxes


def scale(boxes, listed, needs, size):
    """The factor of the boxes: fit - every box under the size of its text;
    picture - the share FIT_SHARE of the states fits its text."""
    by_number = {item.number: item for item in listed}
    ratios = []
    for number, (left, top, right, bottom) in boxes.items():
        item = by_number[number]
        need = needs.get(item.element_id)
        if item.mark or need is None:
            continue
        ratios.append((need[0] / (right - left), need[1] / (bottom - top),
                       item.kind == STATE))
    if not ratios:
        return 1.0
    if size == SIZE_FIT:
        return min(min(w, h) for w, h, _ in ratios)
    fits = sorted(max(w, h) for w, h, state in ratios if state) or \
        sorted(max(w, h) for w, h, _ in ratios)
    return fits[max(0, int(math.ceil(FIT_SHARE * len(fits))) - 1)]


def _needs(graphml):
    """The sizes of the full layout by element id."""
    document = decode(graphml)
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    tree = read(document)
    result = {}
    for element_id in [v.element_id for v in tree.walk()] + \
            [c.element_id for c in tree.comments()]:
        element = document.find_element_by_id(element_id)
        if element is not None and hasattr(element, 'get_geometry_rect') \
                and element.has_geometry():
            rect = element.get_geometry_rect()
            result[element_id] = (rect.width, rect.height)
    return result


def apply(diagram, graphml, boxes, listed, size, routing=ROUTING_ORTHOGONAL):
    """The analysed diagram arranged as the boxes: built without geometry,
    the scaled boxes as absolute rects and points, the arrange layout routed
    as `routing` says; return (document, text)."""
    factor = scale(boxes, listed, _needs(graphml), size)
    by_number = {item.number: item for item in listed}
    document = build(diagram, GEOMETRY_NONE)
    document.set_geometry(CyberiadaML.geometryFormatLegacyYED)
    for number, box in boxes.items():
        item = by_number[number]
        element = document.find_element_by_id(item.element_id)
        if element is None:
            continue
        left, top, right, bottom = (c * factor for c in box)
        if item.mark:
            element.update_geometry(CyberiadaML.Point((left + right) / 2.0,
                                                      (top + bottom) / 2.0))
        else:
            element.update_geometry(CyberiadaML.Rect(left, top, right - left,
                                                     bottom - top))
    document.arrange_geometry(True, routing_of(routing))
    document.convert_geometry(CyberiadaML.geometryFormatQt)
    document.meta().set_geometry(CyberiadaML.geometryDeclarationFull)
    text = encode(document)
    verify(text)
    return document, text
