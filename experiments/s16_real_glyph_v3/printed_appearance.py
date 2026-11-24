"""Appearance of source-scale S16 printed composites after glyph placement."""

import cv2
import numpy as np


def printed_arms(track, *, include_comparison=False):
    """Return the default view first, followed by the requested comparison."""
    if track not in {"modern", "old-print"}:
        raise ValueError(f"Unknown printed track {track!r}")
    return ("raw", "smooth") if include_comparison else ("raw",)


def paint_views(arms, opacity, edges, *, ink, paper, rng):
    """Paint selected views with identical glyph placement and opacity."""
    views = {}
    for arm in arms:
        if arm == "raw":
            views[arm] = np.rint(paper * (1 - opacity) + ink * opacity).astype(np.uint8)
        elif arm == "smooth":
            views[arm] = _normalise_background(opacity, edges, ink, paper, rng)
        else:
            raise ValueError(f"Unknown print appearance {arm!r}")
    return views


def _normalise_background(opacity, edges, ink, paper_level, rng):
    """Blend the paper around glyph patch edges outside the protected ink."""
    paper = np.clip(paper_level + rng.normal(0, .38, opacity.shape), 0, 255)
    image = np.rint(paper * (1 - opacity) + ink * opacity).astype(np.uint8)
    kernel = np.ones((5, 5), np.uint8)
    protected = cv2.dilate(np.uint8(opacity >= .04), kernel) > 0
    seams = (cv2.dilate(edges, kernel) > 0) & ~protected
    seams[:3] = seams[-3:] = False
    seams[:, :3] = seams[:, -3:] = False
    if seams.any():
        yy, xx = np.nonzero(seams)
        center = (int(xx.min() + xx.max() + 1) // 2, int(yy.min() + yy.max() + 1) // 2)
        paper_rgb = cv2.cvtColor(np.rint(paper).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        destination = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        blended = cv2.seamlessClone(paper_rgb, destination, np.uint8(seams) * 255, center, cv2.NORMAL_CLONE)
        image[seams] = blended[..., 0][seams]
    return image
