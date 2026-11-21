"""Renderer and calibration split contracts, using only programmatic fixtures."""
import io
import json

import pytest
from PIL import Image, ImageDraw

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.scanifier_v2 import dev_profiles, fit_dev_profiles


def test_profile_replays_seed_and_preserves_geometry_and_jpeg_tables():
    profile = fit_dev_profiles._old_flatbed(seed=8)
    profile["ranges"].update(scanner_edge_fraction=[0, 0], scanner_bars=[0, 0])
    qtables = [[3] * 64, [5] * 64]
    profile["jpeg_encoders"] = [{"subsampling": 2, "qtables": qtables}]
    image = Image.new("RGB", (120, 150), "white")
    ImageDraw.Draw(image).rectangle((30, 30, 70, 100), fill="black")

    params = dev_profiles.sample_profile(profile)
    encoded = dev_profiles._render(image, params, profile["seed"], None)
    with Image.open(io.BytesIO(encoded)) as decoded:
        assert list(decoded.quantization.values()) == qtables
    a = dev_profiles.apply_profile(image, profile)
    assert a.size == image.size
    assert a.tobytes() == dev_profiles.apply_profile(image, profile, seed=8).tobytes()
    assert a.tobytes() != dev_profiles.apply_profile(image, profile, seed=9).tobytes()
    assert np.asarray(a)[50, 50].max() < 30


def test_manifest_rejects_cross_split_physical_pages(tmp_path):
    files = [tmp_path / f"{index}.jpg" for index in range(2)]
    for path in files:
        path.touch()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "purpose": "non_test_development_calibration",
        "captures": [
            {"profile": "phone_flat", "page": 1, "split": "fit", "file": str(files[0])},
            {"profile": "phone_oblique", "page": 1, "split": "check", "file": str(files[1])},
        ],
    }))
    with pytest.raises(ValueError, match="one split"):
        fit_dev_profiles._manifest(manifest)


def test_distribution_comparison_uses_empirical_cdfs():
    distances = fit_dev_profiles._distances([0, 1, 2], [1, 2, 3])
    assert distances["ks_d"] == pytest.approx(1 / 3)
    assert distances["wasserstein_1"] == pytest.approx(1)
