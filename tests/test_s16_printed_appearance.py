import cv2
import numpy as np

from experiments.s16_real_glyph_v3.printed_appearance import paint_views, printed_arms


def test_modern_default_skips_background_blending(monkeypatch):
    def unexpected_blend(*args, **kwargs):
        raise AssertionError("Modern raw output attempted to blend seams")

    monkeypatch.setattr(cv2, "seamlessClone", unexpected_blend)
    opacity = np.array([[0, .5, 1]], dtype=np.float32)
    views = paint_views(printed_arms("modern"), opacity, None, ink=30, paper=230, rng=None)
    assert tuple(views) == ("raw",)
    assert np.array_equal(views["raw"], np.array([[230, 130, 30]], dtype=np.uint8))


def test_track_comparison_keeps_default_pixels_and_protects_ink(monkeypatch):
    calls = []

    def mark_background(source, target, mask, center, mode):
        calls.append(mask.copy())
        result = target.copy()
        result[mask > 0] = 220
        return result

    monkeypatch.setattr(cv2, "seamlessClone", mark_background)
    opacity = np.zeros((32, 40), dtype=np.float32)
    opacity[12:18, 19:21] = 1
    edges = np.zeros(opacity.shape, dtype=np.uint8)
    edges[10:24, 13] = 1

    def paint(track, compare=False):
        return paint_views(printed_arms(track, include_comparison=compare), opacity, edges,
                           ink=30, paper=230, rng=np.random.default_rng(7))

    modern = paint("modern", compare=True)
    old = paint("old-print")
    old_comparison = paint("old-print", compare=True)
    assert tuple(modern) == ("raw", "smooth")
    assert tuple(old) == ("raw",)
    assert tuple(old_comparison) == ("raw", "smooth")
    assert len(calls) == 2 and all(mask.any() for mask in calls)
    assert all(not mask[opacity > 0].any() for mask in calls)
    assert np.array_equal(old["raw"], old_comparison["raw"])
    assert np.array_equal(modern["raw"], old_comparison["raw"])
    assert np.all(old_comparison["smooth"][opacity > 0] == 30)
    assert np.any(old_comparison["smooth"] != modern["raw"])
