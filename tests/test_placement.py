# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the placement of a diagram as its picture
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

import json
import struct

import pytest

from conftest import PNG, FakeClient, diagram, fenced, png
from hsm_maker import client as C
from hsm_maker import maker as M
from hsm_maker import placement as P
from hsm_maker.cyberiadaml import CyberiadaML
from hsm_maker.language import Texts
from hsm_maker.reader import decode, read

LIFT = diagram('lift.hsm')
EN = Texts('en')
# the picture: the full layout drawn at half its size, 10 px from the corner
PICTURE_SCALE = 0.5
MARGIN = 10.0
WIDTH, HEIGHT = 1200, 600


def _jpeg(width, height):
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + bytes(9)
    sof0 = b'\xff\xc0' + struct.pack('>HBHH', 17, 8, height, width) + \
        bytes(10)
    return b'\xff\xd8' + app0 + sof0


def _webp(chunk, payload):
    return b'RIFF' + bytes(4) + b'WEBP' + chunk + bytes(4) + payload


@pytest.mark.parametrize('data, size', [
    (png(640, 480), (640, 480)),
    (b'GIF89a' + struct.pack('<HH', 321, 123), (321, 123)),
    (_jpeg(800, 600), (800, 600)),
    (_webp(b'VP8 ', bytes(6) + struct.pack('<HH', 300, 200)), (300, 200)),
    (_webp(b'VP8L', b'\x2f' + struct.pack('<I', (299) | (199 << 14))),
     (300, 200)),
    (_webp(b'VP8X', bytes(4) + (299).to_bytes(3, 'little') +
           (199).to_bytes(3, 'little')), (300, 200)),
    (PNG, None), (b'BM', None)])
def test_image_size(data, size):
    assert C.image_size(data) == (tuple(size) if size else None)


def _lift():
    return M.convert(LIFT).document


def test_items():
    listed = P.items(_lift(), EN)
    assert [i.text for i in listed] == [
        '1 machine Lift (its frame)', '2 initial in Lift', '3 state Idle',
        '4 state Moving', '5 state Moving::MovingUp',
        '6 state Moving::MovingDown', '7 state DoorsOpen']
    assert [i.mark for i in listed] == [False, True] + [False] * 5
    text = P.request(EN, listed, WIDTH, HEIGHT)
    assert '1200 x 600 pixels' in text and text.endswith('7 state DoorsOpen')


def _truth(document, listed, swap=()):
    """The boxes of the full layout as a picture: the answer of a model that
    reads it exactly; swap exchanges the places of two numbers."""
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    boxes = {}
    for item in listed:
        element = document.find_element_by_id(item.element_id)
        if item.mark:
            p = element.get_geometry_point()
            box = (p.x, p.y, p.x, p.y)
        else:
            r = element.get_geometry_rect()
            box = (r.x, r.y, r.x + r.width, r.y + r.height)
        boxes[str(item.number)] = [round(c * PICTURE_SCALE + MARGIN, 1)
                                   for c in box]
    if swap:
        a, b = (str(n) for n in swap)
        boxes[a], boxes[b] = boxes[b], boxes[a]
    return '```json\n' + json.dumps(boxes) + '\n```\n'


def test_parse():
    listed = P.items(_lift(), EN)
    boxes = P.parse('the boxes:\n```json\n{"3": [10, 20, 110, 80], '
                    '"7": [500, 590, 400, 700], "2": [5, 5, 5, 5], '
                    '"4": [1, 1, 1, 50], "9": [0, 0, 9, 9], '
                    '"5": [1, 2, 3], "6": ["a", 0, 1, 1], '
                    '"1": [NaN, 0, 1, 1]}\n```', listed, WIDTH, HEIGHT)
    # sorted and clamped, the mark of a point kept, the rest dropped
    assert boxes == {3: (10, 20, 110, 80), 7: (400, 590, 500, 600),
                     2: (5, 5, 5, 5)}
    assert P.parse('so: {"3": [1, 2, 30, 40]} and more', listed,
                   WIDTH, HEIGHT) == {3: (1, 2, 30, 40)}
    for answer, reason in (('no boxes here', 'no JSON object'),
                           ('{"3": [1, 2,}', 'cannot be read'),
                           ('```json\n[1, 2]\n```', 'not a JSON object'),
                           ('{"9": [1, 2, 3, 4]}', 'no box')):
        with pytest.raises(P.PlacementError, match=reason):
            P.parse(answer, listed, WIDTH, HEIGHT)


def test_scale():
    listed = [P.Item(1, 'a', 'state', False, ''),
              P.Item(2, 'b', 'state', False, ''),
              P.Item(3, 'c', 'initial', True, '')]
    boxes = {1: (0, 0, 100, 50), 2: (0, 0, 300, 400), 3: (5, 5, 5, 5)}
    needs = {'a': (300, 200), 'b': (300, 200)}
    assert P.scale(boxes, listed, needs, P.SIZE_FIT) == 0.5
    assert P.scale(boxes, listed, needs, P.SIZE_PICTURE) == 4.0
    assert P.scale({3: (5, 5, 5, 5)}, listed, needs, P.SIZE_FIT) == 1.0


def _centres(graphml):
    document = decode(graphml)
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    tree = read(document)
    result = {}
    for vertex in tree.walk():
        if vertex.kind == 'state' and vertex.parent.kind == 'machine':
            r = document.find_element_by_id(vertex.element_id) \
                .get_geometry_rect()
            result[vertex.name] = (r.x + r.width / 2.0, r.y + r.height / 2.0,
                                   r.width, r.height)
    return result


def _order(centres):
    names = sorted(centres)
    return [(a, b, centres[b][0] > centres[a][0], centres[b][1] > centres[a][1])
            for i, a in enumerate(names) for b in names[i + 1:]]


def _run(answers, size=P.SIZE_FIT):
    client = FakeClient(answers)
    image = C.Image(png(WIDTH, HEIGHT), C.PNG, 'lift.png')
    result = M.run('', client, geometry=P.GEOMETRY_PICTURE, pictures=[image],
                   size=size)
    return result, client


def test_arranged_as_the_picture():
    listed = P.items(_lift(), EN)
    result, client = _run([fenced(LIFT), _truth(_lift(), listed)])
    assert result.ok and result.reason == M.ACCEPTED
    assert (result.placement.placed, result.placement.total,
            result.placement.error) == (7, 7, None)
    assert result.usage.requests == 2
    # the same first message, the accepted answer, the request
    rounds, placing = client.calls[0][1], client.calls[1][1]
    assert placing[0] == rounds[0]
    assert placing[1] == {'role': 'assistant', 'content': fenced(LIFT)}
    assert '1 machine Lift (its frame)' in placing[2]['content']
    assert _order(_centres(result.graphml)) == \
        _order(_centres(M.convert(LIFT).graphml))


def test_swapped_as_the_picture():
    listed = P.items(_lift(), EN)
    # Idle (3) drawn where DoorsOpen (7) is, and the other way round
    result, _ = _run([fenced(LIFT), _truth(_lift(), listed, swap=(3, 7))])
    centres = _centres(result.graphml)
    full = _centres(M.convert(LIFT).graphml)
    assert full['Idle'][0] < full['DoorsOpen'][0]
    assert centres['DoorsOpen'][0] < centres['Idle'][0]


def test_picture_size():
    listed = P.items(_lift(), EN)
    fit, _ = _run([fenced(LIFT), _truth(_lift(), listed)])
    big, _ = _run([fenced(LIFT), _truth(_lift(), listed)], P.SIZE_PICTURE)
    for name, (_, _, w, h) in _centres(big.graphml).items():
        _, _, fw, fh = _centres(fit.graphml)[name]
        assert w >= fw and h >= fh


@pytest.mark.parametrize('answers, reason', [
    ([fenced(LIFT), 'I cannot see the elements'], 'no JSON object'),
    ([fenced(LIFT)], 'no more answers')])
def test_placement_fallback(answers, reason):
    result, _ = _run(answers)
    assert result.ok
    assert result.placement.placed == 0 and reason in result.placement.error
    assert result.graphml == M.convert(LIFT).graphml


def test_without_picture_size():
    client = FakeClient([fenced(LIFT)])
    result = M.run('', client, geometry=P.GEOMETRY_PICTURE,
                   pictures=[C.Image(PNG, C.PNG, 'x.png')])
    assert result.ok and 'size of the picture' in result.placement.error
    assert len(client.calls) == 1


def test_full_without_pictures():
    client = FakeClient([fenced(LIFT)])
    result = M.run('a lift', client, geometry=P.GEOMETRY_PICTURE)
    assert result.ok and result.placement is None
    assert result.graphml == M.convert(LIFT).graphml
