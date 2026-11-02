# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The tests of the likeness tool
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
"""The likeness of a made diagram to its reference (tools/likeness.py)."""
import importlib.util
import os

from conftest import diagram
from hsm_maker import maker as M
from hsm_maker.builder import encode
from hsm_maker.cyberiadaml import CyberiadaML
from hsm_maker.notation import MACHINE
from hsm_maker.reader import decode, read

SPEC = importlib.util.spec_from_file_location(
    'likeness', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                             'tools', 'likeness.py'))
LIKENESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LIKENESS)
SCALE, SHIFT = 1.5, 100.0


def _lift():
    """Lay the lift out: the recorded documents have no geometry."""
    return M.convert(diagram('lift.hsm')).graphml


def _moved(graphml, change):
    """Change every rect and point of a vertex of the document.

    change(x, y, w, h, name) gives the new values.
    """
    document = decode(graphml)
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    for vertex in read(document).walk():
        element = document.find_element_by_id(vertex.element_id)
        if element is None or vertex.kind == MACHINE or \
                not element.has_geometry():
            continue
        if hasattr(element, 'get_geometry_rect'):
            r = element.get_geometry_rect()
            element.update_geometry(CyberiadaML.Rect(
                *change(r.x, r.y, r.width, r.height, vertex.name)))
        else:
            p = element.get_geometry_point()
            x, y, _, _ = change(p.x, p.y, 0.0, 0.0, vertex.name)
            element.update_geometry(CyberiadaML.Point(x, y))
    document.convert_geometry(CyberiadaML.geometryFormatQt)
    return encode(document)


def test_itself():
    """A document is like itself."""
    result = LIKENESS.likeness(_lift(), _lift())
    assert result['matched'] == result['elements'] > 0
    assert result['transitions_matched'] == result['transitions']
    assert (result['order'], result['displacement'], result['iou']) == \
        (1.0, 0.0, 1.0)


def test_scaled_and_shifted():
    """A uniform scale and a shift are fitted away."""
    moved = _moved(_lift(), lambda x, y, w, h, _: (
        SCALE * x + SHIFT, SCALE * y + SHIFT, SCALE * w, SCALE * h))
    result = LIKENESS.likeness(moved, _lift())
    assert result['order'] == 1.0 and result['displacement'] < 0.01
    assert result['iou'] > 0.9 and abs(result['scale'] - 1 / SCALE) < 0.01


def test_swapped():
    """Idle and DoorsOpen exchanged: the order and the places differ."""
    places = {}
    document = decode(_lift())
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    for element in document.get_state_machines()[0].find_elements_by_type(
            CyberiadaML.elementSimpleState):
        r = element.get_geometry_rect()
        places[element.get_name()] = (r.x, r.y)
    swap = {'Idle': 'DoorsOpen', 'DoorsOpen': 'Idle'}

    def change(x, y, w, h, name):
        if name in swap:
            x, y = places[swap[name]]
        return x, y, w, h

    result = LIKENESS.likeness(_moved(_lift(), change), _lift())
    assert result['order'] < 1.0 and result['displacement'] > 0.05
