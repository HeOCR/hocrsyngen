import pytest

from hocrsyngen.printed_glyph_variance import _smooth_edges, vary_glyph

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
