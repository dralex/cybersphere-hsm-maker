# -----------------------------------------------------------------------------
#  Cybersphere HSM Maker
#
#  The likeness of a made diagram to a reference one
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

"""Measure how much a made diagram looks like a reference one.

The reference is the document the picture was drawn from:

    PYTHONPATH=. python3 tools/likeness.py MADE.graphml REFERENCE.graphml

prints a JSON object: the coverage of the reference elements and
transitions (matched by the kind and the qualified name), the order of the
sibling pairs (left of, above, in line - in line under ALIGN of the larger
extent), the displacement of the centres after the uniform scale and the
shift fitted by least squares (a share of the reference diagonal) and the
mean intersection over union of the fitted rects.
"""

import json
import math
import sys

from hsm_maker.cyberiadaml import CyberiadaML
from hsm_maker.notation import MACHINE
from hsm_maker.reader import decode, read

# the share of the larger extent under which two centres are in line, as
# the arrange brings them (libhtreegeom SEED_ALIGN)
ALIGN = 0.25
DIGITS = 3


class Box:  # pylint: disable=too-few-public-methods
    """An element of a document: its key, its container and its geometry."""

    def __init__(self, key, parent, rect):
        """Keep the key, the parent path and the rect (x, y, w, h)."""
        self.key = key
        self.parent = parent
        self.x, self.y, self.w, self.h = rect

    @property
    def centre(self):
        """The centre of the rect, the point itself for a point."""
        return self.x + self.w / 2.0, self.y + self.h / 2.0


def boxes(graphml):
    """The vertices and the transitions of a document: {key: Box}, the set
    of the transition keys (source, target, event)."""
    document = decode(graphml)
    document.convert_geometry(CyberiadaML.geometryFormatLegacyYED)
    tree = read(document)
    result = {}
    for vertex in tree.walk():
        if vertex.kind == MACHINE:
            continue
        element = document.find_element_by_id(vertex.element_id)
        if element is None or not element.has_geometry():
            continue
        key = (vertex.kind, vertex.path)
        parent = vertex.parent.path if vertex.parent is not None else ''
        if hasattr(element, 'get_geometry_rect'):
            r = element.get_geometry_rect()
            result[key] = Box(key, parent, (r.x, r.y, r.width, r.height))
        else:
            p = element.get_geometry_point()
            result[key] = Box(key, parent, (p.x, p.y, 0.0, 0.0))
    edges = set()
    for vertex in tree.walk():
        for t in vertex.transitions:
            if t.target is not None:
                edges.add((vertex.path, t.target.path, t.event))
    return result, edges


def _side(delta, extent):
    if abs(delta) < ALIGN * extent:
        return 0
    return 1 if delta > 0 else -1


def order(made, reference, keys):
    """The share of the sibling pairs placed alike on both axes."""
    agree = total = 0
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if reference[a].parent != reference[b].parent:
                continue
            for axis in (0, 1):
                ra, rb = reference[a], reference[b]
                ma, mb = made[a], made[b]
                ref = _side(rb.centre[axis] - ra.centre[axis],
                            max((ra.w, ra.h)[axis], (rb.w, rb.h)[axis]))
                got = _side(mb.centre[axis] - ma.centre[axis],
                            max((ma.w, ma.h)[axis], (mb.w, mb.h)[axis]))
                agree += ref == got
                total += 1
    return agree / total if total else 1.0


def fit(made, reference, keys):  # pylint: disable=too-many-locals
    """The uniform scale and the shift taking the made centres to the
    reference ones by least squares: (s, dx, dy)."""
    n = float(len(keys))
    mx = sum(made[k].centre[0] for k in keys) / n
    my = sum(made[k].centre[1] for k in keys) / n
    rx = sum(reference[k].centre[0] for k in keys) / n
    ry = sum(reference[k].centre[1] for k in keys) / n
    num = den = 0.0
    for k in keys:
        (ax, ay), (bx, by) = made[k].centre, reference[k].centre
        num += (ax - mx) * (bx - rx) + (ay - my) * (by - ry)
        den += (ax - mx) ** 2 + (ay - my) ** 2
    s = num / den if den > 0.0 else 1.0
    return s, rx - s * mx, ry - s * my


def _iou(a, b):
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if w <= 0.0 or h <= 0.0:
        return 0.0
    inter = w * h
    return inter / (a[2] * a[3] + b[2] * b[3] - inter)


# pylint: disable-next=too-many-locals
def likeness(made_graphml, reference_graphml):
    """The measures of the made document against the reference."""
    made, made_edges = boxes(made_graphml)
    reference, reference_edges = boxes(reference_graphml)
    keys = sorted(k for k in reference if k in made)
    result = {'elements': len(reference), 'matched': len(keys),
              'transitions': len(reference_edges),
              'transitions_matched': len(reference_edges & made_edges)}
    if len(keys) < 2:
        return result
    s, dx, dy = fit(made, reference, keys)
    xs = [b.x for b in reference.values()] + \
        [b.x + b.w for b in reference.values()]
    ys = [b.y for b in reference.values()] + \
        [b.y + b.h for b in reference.values()]
    diagonal = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    shifts, overlaps = [], []
    for k in keys:
        m, r = made[k], reference[k]
        cx, cy = m.centre
        shifts.append(math.hypot(s * cx + dx - r.centre[0],
                                 s * cy + dy - r.centre[1]))
        if m.w > 0.0 and r.w > 0.0:
            fitted = (s * m.x + dx, s * m.y + dy, s * m.w, s * m.h)
            overlaps.append(_iou(fitted, (r.x, r.y, r.w, r.h)))
    result.update({
        'order': round(order(made, reference, keys), DIGITS),
        'displacement': round(sum(shifts) / len(shifts) / diagonal, DIGITS),
        'iou': round(sum(overlaps) / len(overlaps), DIGITS) if overlaps
        else None,
        'scale': round(s, DIGITS)})
    return result


def main(argv):
    """Print the likeness of MADE.graphml to REFERENCE.graphml."""
    if len(argv) != 2:
        print('usage: likeness.py MADE.graphml REFERENCE.graphml',
              file=sys.stderr)
        return 2
    texts = []
    for path in argv:
        with open(path, encoding='utf-8') as stream:
            texts.append(stream.read())
    print(json.dumps(likeness(texts[0], texts[1]), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
