# SPDX-License-Identifier: CC0-1.0
"""Straight, partly relaxed office-paper creases on the v3 paper stock."""

from dataclasses import dataclass
from functools import cached_property
import math
import random

try:
    from .developable import DevelopablePaper
    from .strong_folds import design as strong_design
except ImportError:  # Blender invokes render.py directly.
    from developable import DevelopablePaper
    from strong_folds import design as strong_design


PROFILES = ("diagonal", "half", "parallel", "three-parallel", "crossed", "dog-ear")


def _relaxed_section(width, height, axis, centers, angles, radius, relaxation):
    """Use narrow circular hinges and much broader, unmarked outer-panel arcs."""
    limit = (abs(width * math.cos(math.radians(axis))) + abs(height * math.sin(math.radians(axis)))) / 2
    bends = [(center, angle, radius, True) for center, angle in zip(centers, angles, strict=True)]
    left_gap, right_gap = centers[0] + limit, limit - centers[-1]
    for center, gap, direction in ((centers[0], left_gap, -1), (centers[-1], right_gap, 1)):
        if gap <= radius:
            raise ValueError("A relaxed panel needs room between the hinge and edge")
        bends.append((center + direction * .55 * gap, -relaxation, .62 * gap / math.radians(relaxation), False))
    return tuple(sorted(bends))


@dataclass(frozen=True)
class RoundedCrossPaper:
    """Two orthogonal rounded sections with bounded shear where their slopes overlap.

    Each section preserves its own arc length. Their additive surface has
    nonzero shear where both slopes are nonzero, so angles stay shallow.
    """

    width: float
    height: float
    x_bends: tuple
    y_bends: tuple
    x_initial_deg: float
    y_initial_deg: float
    thickness: float = .00010
    model: str = "rounded_cross"

    @cached_property
    def sections(self):
        return (DevelopablePaper(self.width, self.height, 0., self.x_initial_deg, self.x_bends),
                DevelopablePaper(self.width, self.height, 90., self.y_initial_deg, self.y_bends))

    @property
    def crease_axes(self):
        return (((1., 0.), self.x_bends), ((0., 1.), self.y_bends))

    def world(self, x, y):
        a, b = self.sections
        sx, zx, _ = a.arc_at(x)
        sy, zy, _ = b.arc_at(y)
        return sx, sy, zx + zy - .001

    def at(self, u, v):
        return self.world((u - .5) * self.width, (.5 - v) * self.height)

    def normal(self, u, v):
        a, b = self.sections
        tx = a.arc_at((u - .5) * self.width)[2]
        ty = b.arc_at((.5 - v) * self.height)[2]
        normal = (-math.tan(tx), -math.tan(ty), 1.)
        length = math.sqrt(sum(value * value for value in normal))
        return tuple(value / length for value in normal)

    def perimeter(self, bounds):
        left, top, right, bottom = bounds
        a, b = self.sections
        x = [s / self.width + .5 for s in a.breaks]
        y = [.5 - s / self.height for s in reversed(b.breaks)]
        x = [u for u in x if left < u < right]
        y = [v for v in y if top < v < bottom]
        return ([(u, top) for u in (left, *x)] + [(right, v) for v in (top, *y)]
                + [(u, bottom) for u in (right, *reversed(x))] + [(left, v) for v in (bottom, *reversed(y))])

    def mesh(self):
        a, b = self.sections
        nx, ny = len(a.breaks), len(b.breaks)
        rest = [(x, y) for y in b.breaks for x in a.breaks]
        faces = []
        for j in range(ny - 1):
            for i in range(nx - 1):
                p = j * nx + i
                faces.extend(((p, p + 1, p + nx + 1), (p, p + nx + 1, p + nx)))
        return ([self.world(x, y) for x, y in rest], faces,
                [(x / self.width + .5, y / self.height + .5) for x, y in rest])


def design(base, profile, seed):
    if profile == "dog-ear":
        return strong_design(base, profile, seed)
    width, height = base.width, base.height
    rng = random.Random(seed ^ 0x50A61D)
    radius = rng.uniform(.00031, .00046)
    if profile == "crossed":
        x_angle, y_angle, curl = 9., 10., 1.4
        return RoundedCrossPaper(
            width, height,
            _relaxed_section(width, height, 0., (width * .04,), (x_angle,), radius, curl),
            _relaxed_section(width, height, 90., (height * .06,), (y_angle,), radius, curl),
            -x_angle / 2 + curl, -y_angle / 2 + curl,
        )
    if profile == "diagonal":
        axis, centers, angles = rng.uniform(-48., -37.), (width * .04,), (19.,)
    elif profile == "half":
        axis, centers, angles = 90., (height * .06,), (17.,)
    elif profile == "parallel":
        axis, centers, angles = 90., (-height / 6, height / 6), (14., 12.)
    elif profile == "three-parallel":
        axis, centers, angles = 90., (-height / 4, 0., height / 4), (8., 6., 8.)
    else:
        raise ValueError(f"Unknown rounded fold profile: {profile}")
    curl = 3.4
    bends = _relaxed_section(width, height, axis, centers, angles, radius, curl)
    return DevelopablePaper(width, height, axis, -sum(angles) / 2 + curl, bends)
