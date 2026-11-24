import pytest
from collections import Counter

from hocrsyngen.printed_glyph_variance import (
    _smooth_edges,
    balanced_document_variance,
    document_variance,
    placement_jitter,
    vary_glyph,
)

np = pytest.importorskip("numpy")
ndimage = pytest.importorskip("scipy.ndimage")


def test_repeated_source_glyphs_get_distinct_reproducible_rasters():
    alpha = np.zeros((32, 24), dtype=np.float32)
    alpha[2:29, 4:9] = 0.9
    alpha[2:7, 4:20] = 0.9
    alpha[7:26, 15:20] = 0.9
    original = alpha.copy()
    seen = set()
    variants = [vary_glyph(alpha, seed=733, index=i, seen=seen) for i in range(24)]
    assert len(seen) == len(variants)
    assert len({np.rint(v.opacity * 255).astype(np.uint8).tobytes() for v in variants}) == len(variants)
    for index, variant in enumerate(variants):
        replay = vary_glyph(alpha, seed=733, index=index, seen=set())
        assert replay.raster_sha256 == variant.raster_sha256
        assert variant.opacity.shape == tuple(n + 2 * variant.pad for n in alpha.shape)
        assert 0.978 <= variant.scale <= 1.022
        assert abs(variant.rotation_degrees) <= 1.4
        assert max(abs(variant.warp_x_px), abs(variant.warp_y_px)) <= 0.42
        assert abs(variant.stroke_delta_px) <= 1
        assert 0.95 <= variant.ink_scale <= 1.05
    np.testing.assert_array_equal(alpha, original)


def test_edge_smoothing_preserves_dark_and_gray_interiors():
    alpha = np.zeros((25, 25), dtype=np.float32)
    alpha[6:19, 6:19] = 0.9
    alpha[9:16, 9:16] = 0.62
    alpha[5, 6:19] = 0.3
    smooth = _smooth_edges(alpha, ndimage)
    np.testing.assert_array_equal(alpha[7:18, 7:18], smooth[7:18, 7:18])
    assert np.any(alpha[5, 6:19] != smooth[5, 6:19])
    assert not smooth[0].any()


def test_quantized_duplicate_is_retried():
    alpha = np.zeros((15, 15), dtype=np.float32)
    alpha[3:12, 3:12] = 0.9
    seen = set()
    first = vary_glyph(alpha, seed=733, index=2, seen=seen)
    second = vary_glyph(alpha, seed=733, index=2, seen=seen)
    assert first.attempt == 0
    assert second.attempt > 0
    assert first.raster_sha256 != second.raster_sha256


def test_levels_scale_matching_draws_and_strong_edges_stay_ink_only():
    alpha = np.zeros((33, 25), dtype=np.float32)
    alpha[4:29, 4:20] = .88
    base, middle, stronger = [vary_glyph(alpha, seed=209, index=2, seen=set(), level=level, ink_only=True)
                              for level in ("current", "medium", "strong")]
    assert base.attempt == middle.attempt == stronger.attempt == 0
    for other, factor in ((middle, 2.0), (stronger, 2.75)):
        assert other.scale - 1 == pytest.approx((base.scale - 1) * factor)
        for field in ("rotation_degrees", "warp_x_px", "warp_y_px", "stroke_delta_px"):
            assert getattr(other, field) == pytest.approx(getattr(base, field) * factor)
    distance = ndimage.distance_transform_edt(stronger.opacity < .47)
    assert not stronger.opacity[distance >= 2].any()
    assert placement_jitter(209, 2, "current") == (0., 0.)
    assert placement_jitter(209, 2, "strong") != (0., 0.)


def test_twenty_document_rosters_realise_the_seeded_default_per_track():
    ids = [f"page-{i}" for i in range(20)]
    allocations = []
    for track in ("modern", "old-print"):
        plan = balanced_document_variance(783620, track, ids)
        assert set(plan) == set(ids)
        assert Counter(plan.values()) == {"medium": 13, "strong": 3, "current": 4}
        assert plan == balanced_document_variance(783620, track, reversed(ids))
        assert plan != balanced_document_variance(783621, track, ids)
        allocations.append(plan)
    assert allocations[0] != allocations[1]
    with pytest.raises(ValueError, match="unique"):
        balanced_document_variance(783620, "modern", ["page-1", "page-1"])


def test_standalone_documents_cover_each_level_at_its_default_frequency():
    expected = {"medium": .65, "strong": .15, "current": .20}
    ids = [f"document-{i}" for i in range(2000)]
    for track in ("modern", "old-print"):
        levels = [document_variance(783620, track, ident) for ident in ids]
        assert levels == [document_variance(783620, track, ident) for ident in ids]
        assert all(Counter(levels)[level] / len(ids) == pytest.approx(weight, abs=.04)
                   for level, weight in expected.items())
