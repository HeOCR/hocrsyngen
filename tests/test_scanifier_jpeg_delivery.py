import hashlib
import io

import numpy as np
import pytest
from PIL import Image

from experiments.scanifier_v2.delivery import apply_jpeg_delivery, fit_jpeg_delivery
from experiments.scanifier_v2.phone_training import (
    PhoneView,
    phone_annotations,
    phone_line_crop,
    phone_warp,
)


def jpeg(size, *, sampling=0, quality=75, orientation=1, pixels=None):
    if pixels is None:
        pixels = Image.effect_noise(size, 50).convert("RGB")
    pixels = pixels.resize(size, Image.Resampling.LANCZOS)
    exif = Image.Exif()
    exif[274] = orientation
    recipe = io.BytesIO()
    pixels.save(recipe, format="JPEG", subsampling=sampling, quality=quality, exif=exif)
    return recipe.getvalue()


def fit(original, delivered):
    return fit_jpeg_delivery(
        original,
        delivered,
        original_sha256=hashlib.sha256(original).hexdigest(),
        delivered_sha256=hashlib.sha256(delivered).hexdigest(),
    )


def test_delivery_replays_jpeg_and_preserves_projection():
    original = jpeg((640, 480))
    with Image.open(io.BytesIO(original)) as image:
        delivered = jpeg((320, 240), sampling=2, quality=53, pixels=image)
    endpoint = fit(original, delivered)
    assert endpoint.subsampling == 2
    assert endpoint.long_edge == 320
    with Image.open(io.BytesIO(delivered)) as image:
        assert endpoint.qtables == tuple(map(tuple, image.quantization.values()))

    size = (640, 480)
    lines = ({"box": [90, 80, 410, 110], "text": "42 שלום"},)
    warp = phone_warp(
        size, size=size, quad=((0.14, 0.12), (0.85, 0.22), (0.91, 0.88), (0.08, 0.89))
    )
    with Image.open(io.BytesIO(original)) as image:
        raster = image.copy()
    view = PhoneView(raster, phone_annotations(lines, warp, size), warp, {})
    result = apply_jpeg_delivery(view, lines, size, [endpoint], seed=17)
    replay = apply_jpeg_delivery(view, lines, size, [endpoint], seed=17)
    assert result.parameters == replay.parameters
    assert result.image.tobytes() == replay.image.tobytes()
    assert result.image.size == (320, 240)
    assert not result.image.getexif()
    xy = [[90, 80], [410, 110]]
    np.testing.assert_allclose(result.warp.forward(xy), warp.forward(xy) / 2)
    assert result.lines[0]["text"] == lines[0]["text"]
    assert result.lines[0]["min_local_height"] < view.lines[0]["min_local_height"]
    crop, reason = phone_line_crop(result, 0, minimum_height=9)
    assert crop is not None and reason is None
    assert phone_line_crop(result, 0, minimum_height=20) == (None, "underresolved")


@pytest.mark.parametrize("size", [(640, 480), (320, 320), (320, 300)])
def test_delivery_rejects_unidentified_size_cap_and_changed_framing(size):
    with pytest.raises(ValueError, match="whole-frame downsample"):
        fit(jpeg((640, 480)), jpeg(size))


def test_delivery_rejects_bad_hash_and_orientation():
    original = jpeg((640, 480))
    delivered = jpeg((320, 240))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        fit_jpeg_delivery(
            original, delivered, original_sha256="0" * 64, delivered_sha256="1" * 64
        )
    with pytest.raises(ValueError, match="upright"):
        fit(original, jpeg((320, 240), orientation=6))
