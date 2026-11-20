"""Invertible capture geometry in pixel-edge coordinates."""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np


def project(matrix, points):
    points = np.asarray(points, dtype=float)
    homogeneous = points @ matrix[:, :2].T + matrix[:, 2]
    return homogeneous[..., :2] / homogeneous[..., 2:]


def corners(size):
    w, h = size
    return [(0, 0), (w, 0), (w, h), (0, h)]


def exif_transform(size, orientation):
    """Map stored pixel edges to the orientation produced by exif_transpose."""
    w, h = size
    transforms = {
        1: ((1, 0, 0), (0, 1, 0)),
        2: ((-1, 0, w), (0, 1, 0)),
        3: ((-1, 0, w), (0, -1, h)),
        4: ((1, 0, 0), (0, -1, h)),
        5: ((0, 1, 0), (1, 0, 0)),
        6: ((0, -1, h), (1, 0, 0)),
        7: ((0, -1, h), (-1, 0, w)),
        8: ((0, 1, 0), (-1, 0, w)),
    }
    return np.array([*transforms.get(orientation, transforms[1]), (0, 0, 1)], dtype=float)


def _split_edges(points, axis, knots, closed):
    vertices = list(points)
    result = []
    for start, end in pairwise(vertices + ([vertices[0]] if closed else [])):
        result.append(start)
        delta = end - start
        if delta[axis]:
            fractions = (knots - start[axis]) / delta[axis]
            for t in sorted(fractions[(fractions > 0) & (fractions < 1)]):
                result.append(start + t * delta)
    if not closed:
        result.append(vertices[-1])
    return np.array(result)


@dataclass(frozen=True)
class Warp:
    """EXIF → horizontal shear → vertical shear → camera homography.

    Each shear is piecewise linear and inverted by subtraction. Splitting
    polylines at the shear knots before projection preserves their exact shape
    under the same map used to sample the raster.
    """

    exif: np.ndarray
    x_knots: np.ndarray
    x_offsets: np.ndarray
    y_knots: np.ndarray
    y_offsets: np.ndarray
    camera: np.ndarray
    size: tuple[int, int]

    def _shear_x(self, points, sign=1):
        points[..., 0] += sign * np.interp(points[..., 1], self.x_knots, self.x_offsets)

    def _shear_y(self, points, sign=1):
        points[..., 1] += sign * np.interp(points[..., 0], self.y_knots, self.y_offsets)

    def forward(self, points):
        points = project(self.exif, points)
        self._shear_x(points)
        self._shear_y(points)
        return project(self.camera, points)

    def inverse(self, points):
        points = project(np.linalg.inv(self.camera), points)
        self._shear_y(points, -1)
        self._shear_x(points, -1)
        return project(np.linalg.inv(self.exif), points)

    def path(self, points, *, closed=True):
        points = project(self.exif, points)
        if np.any(self.x_offsets):
            points = _split_edges(points, 1, self.x_knots, closed)
            self._shear_x(points)
        if np.any(self.y_offsets):
            points = _split_edges(points, 0, self.y_knots, closed)
            self._shear_y(points)
        return project(self.camera, points)

    def record(self):
        return {
            "exif_matrix": self.exif.tolist(),
            "horizontal_shear": np.column_stack((self.x_knots, self.x_offsets)).tolist(),
            "vertical_shear": np.column_stack((self.y_knots, self.y_offsets)).tolist(),
            "camera_matrix": self.camera.tolist(),
        }


def make_warp(source_size, orientation, p):
    exif = exif_transform(source_size, orientation)
    w, h = source_size[::-1] if orientation in (5, 6, 7, 8) else source_size
    length = max(w, h)
    t = np.linspace(0, 1, 33)
    # Smoothly bowed page with a smaller alternating displacement from folds.
    x_offsets = p["crumple"] * length * np.sin(
        2 * np.pi * p["crumple_cycles"] * t + np.deg2rad(p["crumple_phase_deg"])
    )
    y_offsets = length * (
        p["curl"] * (4 * (t - 0.5) ** 2 - 0.5)
        + 0.45 * p["crumple"] * np.sin(2 * np.pi * p["crumple_cycles"] * t)
    )
    pitch, yaw, roll = np.deg2rad([p["pitch_deg"], p["yaw_deg"], p["roll_deg"]])
    cx, sx = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cr, sr = np.cos(roll), np.sin(roll)
    turn = p["quarter_turn"] // 90
    turn_cos, turn_sin = (1, 0, -1, 0)[turn], (0, 1, 0, -1)[turn]
    c, s = cr * turn_cos - sr * turn_sin, sr * turn_cos + cr * turn_sin
    # Pinhole projection of the tilted plane. Image y increases downward.
    tilt = np.array([[cy, sy * sx, 0], [0, cx, 0], [-sy, cy * sx, p["distance"]]])
    rotate = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    center = np.array([[1 / length, 0, -w / (2 * length)],
                       [0, 1 / length, -h / (2 * length)], [0, 0, 1]])
    camera = rotate @ tilt @ center
    warp = Warp(exif, t * h, x_offsets, t * w, y_offsets, camera, source_size)
    boundary = warp.path(corners(source_size))
    low, high = boundary.min(axis=0), boundary.max(axis=0)
    span = high - low
    length = p["long_edge_px"]
    short = round(length * p["frame_aspect"])
    size = (length, short) if span[0] >= span[1] else (short, length)
    pixel_margin = p["margin"] * short
    scale = np.min((np.asarray(size) - 2 * pixel_margin) / span)
    offset = (size - scale * (low + high)) / 2
    frame = np.array([[scale, 0, offset[0]], [0, scale, offset[1]], [0, 0, 1]])
    return Warp(exif, t * h, x_offsets, t * w, y_offsets, frame @ camera, size)


def transform_annotation(record, warp):
    """Transform a line or region, retaining text, order and non-geometric fields."""
    result = dict(record)
    if "polygon" in record:
        result["polygon"] = warp.path(record["polygon"]).tolist()
    if "box" in record:
        left, top, right, bottom = record["box"]
        boundary = warp.path([(left, top), (right, top), (right, bottom), (left, bottom)])
        result["box_polygon"] = boundary.tolist()
    else:
        boundary = np.asarray(result["polygon"])
    low, high = boundary.min(axis=0), boundary.max(axis=0)
    result["box"] = [*np.floor(low).astype(int).tolist(), *np.ceil(high).astype(int).tolist()]
    if "baseline" in record:
        result["baseline"] = warp.path(record["baseline"], closed=False).tolist()
    return result
