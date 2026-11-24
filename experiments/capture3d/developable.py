# SPDX-License-Identifier: CC0-1.0
"""Cut a developable sheet into straight bands of plane and circular cylinder."""

from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property
import math
import random


@dataclass(frozen=True)
class DevelopablePaper:
    width: float
    height: float
    axis_deg: float
    initial_deg: float
    # Cross-sheet arclength in metres, angle through the arc, radius in metres, crease memory.
    bends: tuple
    thickness: float = .00010
    model: str = "developable"

    @cached_property
    def axis(self):
        angle = math.radians(self.axis_deg)
        return math.cos(angle), math.sin(angle)

    @cached_property
    def corners(self):
        x, y = self.width / 2, self.height / 2
        return ((-x, -y), (x, -y), (x, y), (-x, y))

    def cross(self, x, y):
        nx, ny = self.axis
        return nx * x + ny * y

    @cached_property
    def section(self):
        """Exact arclength samples of a constant-curvature strip, including all tangencies."""
        lo, hi = -max(self.cross(*p) for p in self.corners), max(self.cross(*p) for p in self.corners)
        angle = math.radians(self.initial_deg)
        rows = [(lo, lo, 0., angle)]

        def flat(s):
            previous, x, z, theta = rows[-1]
            distance = s - previous
            if distance > 1e-12:
                rows.append((s, x + distance * math.cos(theta), z + distance * math.sin(theta), theta))

        for center, amount, radius, _ in sorted(self.bends):
            delta = math.radians(amount)
            extent = radius * abs(delta)
            start = center - extent / 2
            if not radius > 0 or not extent or start < rows[-1][0] - 1e-12 or start + extent > hi:
                raise ValueError("Paper bends must be positive-radius, non-overlapping, and inside the sheet")
            flat(start)
            signed_radius = math.copysign(radius, delta)
            steps = max(4, math.ceil(abs(amount) / 2.4))
            for i in range(1, steps + 1):
                _, x, z, theta = rows[-1]
                target = theta + delta / steps
                rows.append((start + extent * i / steps, x + signed_radius * (math.sin(target) - math.sin(theta)),
                             z + signed_radius * (math.cos(theta) - math.cos(target)), target))
        flat(hi)
        low = min(row[2] for row in rows)
        return tuple((s, x, z - low + .001, theta) for s, x, z, theta in rows)

    @cached_property
    def breaks(self):
        return tuple(row[0] for row in self.section)

    def arc_at(self, s):
        i = min(len(self.breaks) - 2, max(0, bisect_right(self.breaks, s) - 1))
        a, b = self.section[i:i + 2]
        f = (s - a[0]) / (b[0] - a[0])
        return tuple(left + (right - left) * f for left, right in zip(a[1:], b[1:]))

    def world(self, x, y):
        nx, ny = self.axis
        along = -ny * x + nx * y
        cross, z, _ = self.arc_at(self.cross(x, y))
        return nx * cross - ny * along, ny * cross + nx * along, z

    def at(self, u, v):
        return self.world((u - .5) * self.width, (.5 - v) * self.height)

    def normal(self, u, v):
        nx, ny = self.axis
        _, _, angle = self.arc_at(self.cross((u - .5) * self.width, (.5 - v) * self.height))
        return -nx * math.sin(angle), -ny * math.sin(angle), math.cos(angle)

    def perimeter(self, bounds):
        left, top, right, bottom = bounds
        corners = ((left, top), (right, top), (right, bottom), (left, bottom))
        result = []
        for a, b in zip(corners, (*corners[1:], corners[0]), strict=True):
            sa, sb = (self.cross((u - .5) * self.width, (.5 - v) * self.height) for u, v in (a, b))
            fractions = (sorted((s - sa) / (sb - sa) for s in self.breaks if min(sa, sb) + 1e-12 < s < max(sa, sb) - 1e-12)
                         if abs(sb - sa) > 1e-12 else [])
            result.extend((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])) for f in (0, *fractions))
        return result

    def _clip(self, polygon, bound, sign):
        if not polygon:
            return []
        result = []
        for a, b in zip(polygon, (*polygon[1:], polygon[0]), strict=True):
            da, db = (sign * (self.cross(*p) - bound) for p in (a, b))
            if da >= -1e-12:
                result.append(a)
            if (da > 1e-12 and db < -1e-12) or (da < -1e-12 and db > 1e-12):
                f = da / (da - db)
                result.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
        return result

    def mesh(self):
        rest, faces, indices = [], [], {}
        for a, b in zip(self.breaks[:-1], self.breaks[1:], strict=True):
            polygon = self._clip(self._clip(self.corners, a, 1), b, -1)
            order = []
            for x, y in polygon:
                key = (round(x, 12), round(y, 12))
                if key not in indices:
                    indices[key] = len(rest)
                    rest.append(key)
                order.append(indices[key])
            faces.extend((order[0], order[i], order[i + 1]) for i in range(1, len(order) - 1))
        return ([self.world(x, y) for x, y in rest], faces,
                [(x / self.width + .5, y / self.height + .5) for x, y in rest])


def paper_model(record):
    """Load a serialized render paper without changing the v1/v2 contract."""
    if record.get("model") == "developable":
        return DevelopablePaper(**record)
    if record.get("model") == "cross_creased":
        try:
            from .strong_folds import CrossCreasedPaper
        except ImportError:  # Blender invokes render.py directly.
            from strong_folds import CrossCreasedPaper
        return CrossCreasedPaper(**record)
    try:
        from .geometry import Paper
    except ImportError:  # Blender invokes render.py directly.
        from geometry import Paper
    return Paper(**record)


def from_capture(legacy, mode, realism, seed, *, facing=False):
    rng = random.Random(seed ^ 0x793800)
    profile = realism["fold"]["profile"]
    width, height = legacy.width, legacy.height

    def radius():
        return rng.uniform(.00023, .00047)

    if mode == "book":
        arc = (math.radians(48) * .043)
        bends = [(-width / 2 + arc / 2 + .001, 48., .043, False)]
        if not facing:
            bends.append((width * .21, rng.uniform(8, 14), radius(), True))
        return DevelopablePaper(width, height, 0., -48., tuple(bends))
    if "dog-ear" in profile:
        sx, sy = legacy.dogear_corner
        high = (width + height) / (2 * math.sqrt(2))
        span = (legacy.dogear_size or .038) / math.sqrt(2)
        bends = [(high - span, rng.uniform(28, 48), radius(), True)]
        if "crumple" in profile:
            bends.insert(0, (high - span * 2.3, rng.uniform(8, 14), radius(), True))
        return DevelopablePaper(width, height, math.degrees(math.atan2(sy, sx)), 0., tuple(bends))
    if profile == "double fold":
        initial, bends = 0., [(-.046, 23., radius(), True), (.036, -29., radius(), True)]
    elif profile == "crumple":
        initial, bends = 0., [(-.034, 20., radius(), True), (-.010, -31., radius(), True), (.040, 13., radius(), True)]
    elif profile == "deep crease":
        angle = rng.uniform(18, 27)
        initial, bends = -angle / 2, [(rng.uniform(-.022, .024), angle, radius(), True)]
    else:
        initial, bends = 0., [(height * .27, rng.uniform(7, 13), radius(), True)]
    axis = -90 if profile == "light curl" else rng.choice((-90, 90)) + rng.uniform(-8, 8)
    return DevelopablePaper(width, height, axis, initial, tuple(bends))
