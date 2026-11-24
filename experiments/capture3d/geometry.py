# SPDX-License-Identifier: CC0-1.0
"""Page mesh, UV interpolation and camera distortion shared by the capture pipeline."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Paper:
    width: float = .210
    height: float = .297
    curl: float = .0
    spine: float = .0
    crease_u: float = .55
    crease_angle: float = .0
    crease_width: float = .03
    crease_height: float = .0
    crumple: float = .0
    phase: float = .0
    thickness: float = .00014
    divisions: tuple = (48, 64)

    def shape(self, u, v):
        x, y = (u - .5) * self.width, (.5 - v) * self.height
        z = .0015 + self.curl * (2 * u - 1) ** 2
        z += self.spine * math.exp(-10 * u)
        crease = (u - self.crease_u + (v - .5) * self.crease_angle) / self.crease_width
        z += self.crease_height * math.exp(-abs(crease))
        z += self.crumple * (1 + math.sin(19 * u + 8 * v + self.phase) * math.sin(14 * v - 6 * u)) / 2
        return x, y, z

    def mesh(self):
        nx, ny = self.divisions
        coordinates = [self.shape(x / nx, y / ny) for y in range(ny + 1) for x in range(nx + 1)]
        uvs = [(x / nx, 1 - y / ny) for y in range(ny + 1) for x in range(nx + 1)]
        faces = []
        for j in range(ny):
            for i in range(nx):
                top = j * (nx + 1) + i
                bottom = top + nx + 1
                faces.extend(((top, bottom, bottom + 1), (top, bottom + 1, top + 1)))
        return coordinates, faces, uvs

    def at(self, u, v):
        """Evaluate UV on the actual piecewise planar mesh."""
        nx, ny = self.divisions
        i, j = min(int(u * nx), nx - 1), min(int(v * ny), ny - 1)
        x, y = u * nx - i, v * ny - j
        start = self.shape(i / nx, j / ny)
        end = self.shape((i + 1) / nx, (j + 1) / ny)
        if x >= y:
            middle, weights = self.shape((i + 1) / nx, j / ny), (1 - x, x - y, y)
        else:
            middle, weights = self.shape(i / nx, (j + 1) / ny), (1 - y, y - x, x)
        return tuple(a * weights[0] + b * weights[1] + c * weights[2] for a, b, c in zip(start, middle, end))

    def perimeter(self, bounds):
        """Follow every triangle crossing along the four UV box edges."""
        left, top, right, bottom = bounds
        nx, ny = self.divisions

        def breaks(lo, hi, constant, steps, other):
            offset = (constant * other) % 1
            candidates = (point for i in range(steps) for point in (i / steps, (i + offset) / steps))
            return [lo, *sorted({point for point in candidates if lo < point < hi}), hi]

        a = [(x, top) for x in breaks(left, right, top, nx, ny)[:-1]]
        b = [(right, y) for y in breaks(top, bottom, right, ny, nx)[:-1]]
        c = [(x, bottom) for x in reversed(breaks(left, right, bottom, nx, ny)[1:])]
        d = [(left, y) for y in reversed(breaks(top, bottom, left, ny, nx)[1:])]
        return a + b + c + d


def distort(x, y, width, height, k1):
    """Forward Brown radial projection in top-left image-edge coordinates."""
    cx, cy, scale = width / 2, height / 2, max(width, height) / 2
    dx, dy = x - cx, y - cy
    factor = 1 + k1 * ((dx / scale) ** 2 + (dy / scale) ** 2)
    return cx + dx * factor, cy + dy * factor


def undistort(x, y, width, height, k1):
    """Invert the same radial projection. Works on floats and NumPy grids."""
    cx, cy, scale = width / 2, height / 2, max(width, height) / 2
    dx, dy = x - cx, y - cy
    rd2 = (dx / scale) ** 2 + (dy / scale) ** 2
    factor = 1.0
    for _ in range(8):
        factor -= (factor + k1 * rd2 * factor ** 3 - 1) / (1 + 3 * k1 * rd2 * factor ** 2)
    return cx + dx * factor, cy + dy * factor
