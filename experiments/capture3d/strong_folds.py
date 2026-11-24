# SPDX-License-Identifier: CC0-1.0
"""Straight cylindrical hinges and isometric crossing creases for office paper."""

from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property
import math
import random

try:
    from .developable import DevelopablePaper
except ImportError:  # Blender invokes render.py directly.
    from developable import DevelopablePaper


PROFILES = ("trifold", "quarter", "crossed", "crumple", "dog-ear")


def _cut_x(polygon, x, sign):
    clipped = []
    for a, b in zip(polygon, (*polygon[1:], polygon[0]), strict=True):
        da, db = sign * (a[0] - x), sign * (b[0] - x)
        if da >= 0:
            clipped.append(a)
        if da * db < 0:
            clipped.append((x, a[1] + (b[1] - a[1]) * da / (da - db)))
    return clipped


def _interval(knots, value):
    i = max(0, min(len(knots) - 2, bisect_right(knots, value) - 1))
    fraction = (value - knots[i]) / (knots[i + 1] - knots[i])
    return i, fraction


def _lerp(values, i, fraction):
    return values[i] + fraction * (values[i + 1] - values[i])


@dataclass(frozen=True)
class CrossCreasedPaper:
    """Miura-style panels with irregular width, row depth, and shear.

    Each rest panel has an across vector (dx, 0, 0) and row vector
    (ds, dy, 0). Alternating its inclination preserves the across length;
    expanding the row shear by 1/cos(angle) preserves the dot product.
    Shortening its y component then preserves the row-vector length.
    Every panel is rigid, including the panels at a crossing.
    """

    width: float
    height: float
    profile: str
    columns: tuple
    rows: tuple
    shear: tuple
    inclination_deg: float
    thickness: float = .00010
    model: str = "cross_creased"

    # Planar facets meet at sharp contacts. The same v3 stock and ink shader
    # still applies, with no infinite parallel whitening bands on these facets.
    axis = (1., 0.)
    bends = ()

    @cached_property
    def placement(self):
        angle = math.radians(self.inclination_deg)
        scale, rise = math.cos(angle), math.sin(angle)
        across = [scale * x for x in self.columns]
        depth = [0.]
        for i, (a, b) in enumerate(zip(self.columns, self.columns[1:])):
            depth.append(depth[-1] + (-1 if i % 2 == 0 else 1) * (b - a) * rise)
        offset = [s / scale for s in self.shear]
        along = [0.]
        for y0, y1, s0, s1 in zip(self.rows, self.rows[1:], self.shear, self.shear[1:]):
            dy, ds = y1 - y0, s1 - s0
            along.append(along[-1] + math.sqrt(dy**2 + ds**2 - (ds / scale)**2))
        center = along[-1] / 2
        return across, [y - center for y in along], offset, depth

    @cached_property
    def elevation(self):
        # Clamp against the actual trimmed sheet, including crease/edge intersections.
        return .001 - min(self._unshifted(*point)[2] for panel in self.panels for point in panel)

    def _unshifted(self, x, y):
        across, along, offset, depth = self.placement
        j, fy = _interval(self.rows, y)
        cross = x - _lerp(self.shear, j, fy)
        i, fx = _interval(self.columns, cross)
        return _lerp(across, i, fx) + _lerp(offset, j, fy), _lerp(along, j, fy), _lerp(depth, i, fx)

    def world(self, x, y):
        px, py, pz = self._unshifted(x, y)
        return px, py, pz + self.elevation

    def at(self, u, v):
        return self.world((u - .5) * self.width, (.5 - v) * self.height)

    @cached_property
    def panels(self):
        result = []
        for y0, y1, s0, s1 in zip(self.rows, self.rows[1:], self.shear, self.shear[1:]):
            for a, b in zip(self.columns, self.columns[1:]):
                panel = [(a + s0, y0), (b + s0, y0), (b + s1, y1), (a + s1, y1)]
                panel = _cut_x(panel, -self.width / 2, 1)
                if panel:
                    panel = _cut_x(panel, self.width / 2, -1)
                if len(panel) >= 3:
                    result.append(panel)
        return result

    def mesh(self):
        indices, faces = {}, []
        for panel in self.panels:
            order = []
            for x, y in panel:
                key = (round(x, 12), round(y, 12))
                if key not in indices:
                    indices[key] = len(indices)
                order.append(indices[key])
            faces.extend((order[0], order[i], order[i + 1]) for i in range(1, len(order) - 1)
                         if len({order[0], order[i], order[i + 1]}) == 3)
        return ([self.world(x, y) for x, y in indices], faces,
                [(x / self.width + .5, y / self.height + .5) for x, y in indices])

    def perimeter(self, bounds):
        left, top, right, bottom = bounds
        corners = ((left, top), (right, top), (right, bottom), (left, bottom))
        result = []
        for (u0, v0), (u1, v1) in zip(corners, (*corners[1:], corners[0]), strict=True):
            x0, x1 = (u0 - .5) * self.width, (u1 - .5) * self.width
            y0, y1 = (.5 - v0) * self.height, (.5 - v1) * self.height
            breaks = [0., 1.]
            if y0 != y1:
                breaks.extend((y - y0) / (y1 - y0) for y in self.rows if min(y0, y1) < y < max(y0, y1))
                breaks.sort()

            def cross(t):
                j, f = _interval(self.rows, y0 + (y1 - y0) * t)
                return x0 + (x1 - x0) * t - _lerp(self.shear, j, f)

            for a, b in zip(breaks, breaks[1:]):
                ca, cb = cross(a), cross(b)
                fractions = [a]
                fractions.extend(a + (b - a) * (c - ca) / (cb - ca)
                                 for c in self.columns if min(ca, cb) < c < max(ca, cb))
                result.extend((u0 + t * (u1 - u0), v0 + t * (v1 - v0)) for t in sorted(fractions))
        return result


def design(base, profile, seed):
    """Add a stronger crease design while preserving the v3 stock and caliper."""
    width, height = base.width, base.height
    rng = random.Random(seed ^ 0x951734)
    if profile == "trifold":
        # Two narrow-radius bends lift the outer panels on either side of a flat centre.
        bends = ((-height / 6, 29., .00034, True), (height / 6, 24., .00029, True))
        return DevelopablePaper(width, height, 90., -29., bends)
    if profile == "dog-ear":
        # Both hinge lines are inside the blank outer corner.
        high = (width + height) / (2 * math.sqrt(2))
        scale = min(1., width / .13, height / .13)
        bends = ((high - .031 * scale, 78., .00029, True), (high - .013 * scale, 19., .00025, True))
        return DevelopablePaper(width, height, -45., 0., bends)

    scale = min(1., width / .21, height / .25)
    if profile == "quarter":
        interior_x, interior_y = (-.005,), (.012,)
        shear, angle = (-.014, .032, -.014), 27.
    elif profile == "crossed":
        interior_x, interior_y = (-.039, .009, .066), (-.052, .022, .088)
        shear, angle = (-.007, .027, -.028, .024, -.004), 22.
    elif profile == "crumple":
        interior_x = tuple(width * (i / 7 - .5 + rng.uniform(-.033, .033)) for i in range(1, 7))
        interior_y = tuple(height * (i / 8 - .5 + rng.uniform(-.036, .036)) for i in range(1, 8))
        shear = tuple((-1)**i * rng.uniform(.005, .019) for i in range(9))
        angle = rng.uniform(14., 19.)
    else:
        raise ValueError(f"Unknown strong fold profile: {profile}")
    shear = tuple(shift * scale for shift in shear)
    if profile != "crumple":
        interior_x = tuple(x * scale for x in interior_x)
        interior_y = tuple(y * scale for y in interior_y)
    # Extend the underlying lattice in x, then cut it to the exact rectangle.
    margin = max(abs(s) for s in shear) + .001
    columns = (-width / 2 - margin, *interior_x, width / 2 + margin)
    rows = (-height / 2, *interior_y, height / 2)
    return CrossCreasedPaper(width, height, profile, columns, rows, shear, angle)
