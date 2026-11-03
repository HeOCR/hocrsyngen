import json
from pathlib import Path

import pytest
from PIL import Image

from hocrsyngen.generator import generate_batch
from hocrsyngen.validation import BatchValidationError, validate_batch


def test_pair_keeps_baseline_and_geometry_identical_and_is_deterministic(tmp_path):
    plain, paired, repeat = (tmp_path / x for x in ("plain", "paired", "repeat"))
    for target, pair in ((plain, False), (paired, True), (repeat, True)):
        generate_batch(4, 42, target, ["printed_letter", "handwritten_note", "archive_card", "ledger"],
                       emit_line_annotations=True, emit_paired_render=pair)
        validate_batch(target)
    for name in ("generation_manifest.json", "line_annotations.json"):
        assert (plain / name).read_bytes() == (paired / name).read_bytes() == (repeat / name).read_bytes()
    sidecar = json.loads((paired / "paired_render.json").read_text())
    assert len(sidecar["pages"]) == 4
    assert (paired / "paired_render.json").read_bytes() == (repeat / "paired_render.json").read_bytes()
    manifest = json.loads((plain / "generation_manifest.json").read_text())
    for sample, item in zip(manifest["samples"], sidecar["pages"]):
        src = sample["pages"][0]["asset_path"]
        assert (plain / src).read_bytes() == (paired / src).read_bytes() == (repeat / src).read_bytes()
        assert (paired / item["pair_path"]).read_bytes() == (repeat / item["pair_path"]).read_bytes()
        with Image.open(paired / item["pair_path"]) as img:
            assert img.format == "PNG" and img.size == (item["width"], item["height"])


def test_validation_rejects_tampered_asset_and_bindings(tmp_path):
    generate_batch(1, 11, tmp_path, ["ledger"], emit_paired_render=True)
    path = tmp_path / "paired_render.json"
    payload = json.loads(path.read_text())
    valid = path.read_bytes()
    for field, value in (("source_sha256", "0" * 64), ("pair_path", "../outside.png"), ("pair_path", "assets//pair.png"),
                         ("pair_sha256", "0" * 64), ("width", 1)):
        altered = json.loads(valid)
        altered["pages"][0][field] = value
        path.write_text(json.dumps(altered))
        with pytest.raises(BatchValidationError):
            validate_batch(tmp_path)
    path.write_bytes(valid)
    asset = tmp_path / payload["pages"][0]["pair_path"]
    asset.write_bytes(asset.read_bytes() + b"tampered")
    with pytest.raises(BatchValidationError):
        validate_batch(tmp_path)


def test_validation_rejects_missing_duplicate_nonfinite_and_symlink_escape(tmp_path):
    batch = tmp_path / "batch"
    generate_batch(2, 12, batch, ["ledger"], emit_paired_render=True)
    side = batch / "paired_render.json"
    original = json.loads(side.read_text())
    variants = []
    missing = json.loads(json.dumps(original)); missing["pages"].pop(); variants.append(missing)
    duplicate = json.loads(json.dumps(original)); duplicate["pages"][1] = duplicate["pages"][0]; variants.append(duplicate)
    stale = json.loads(json.dumps(original)); stale["generation_manifest_sha256"] = "0" * 64; variants.append(stale)
    badparam = json.loads(json.dumps(original)); badparam["pages"][0]["parameters"]["rotation_degrees"] = float("nan"); variants.append(badparam)
    outside = tmp_path / "external.png"
    outside.write_bytes((batch / original["pages"][0]["pair_path"]).read_bytes())
    (batch / "link.png").symlink_to(outside)
    escape = json.loads(json.dumps(original)); escape["pages"][0]["pair_path"] = "link.png"; variants.append(escape)
    for payload in variants:
        side.write_text(json.dumps(payload))
        with pytest.raises(BatchValidationError):
            validate_batch(batch)


def test_capture_is_actual_rotated_raster_without_rng_drift():
    import random
    from PIL import ImageDraw
    from hocrsyngen.generator import _condition_bundle, _degrade

    image = Image.new("RGB", (32, 32), "white")
    ImageDraw.Draw(image).rectangle((4, 7, 15, 24), fill="black")
    normal_rng, pair_rng = random.Random(42), random.Random(42)
    plain = _degrade(image, normal_rng, (255, 255, 255), "office_scan_soft", _condition_bundle(None))
    capture = {}
    paired = _degrade(image, pair_rng, (255, 255, 255), "office_scan_soft", _condition_bundle(None),
                      pair_capture=capture)
    expected = image.rotate(capture["rotation_degrees"], resample=Image.Resampling.BICUBIC,
                            expand=False, fillcolor=(255, 255, 255))
    assert capture["image"].tobytes() == expected.tobytes()
    assert paired.tobytes() == plain.tobytes()
    assert pair_rng.getstate() == normal_rng.getstate()


def test_broken_and_external_sidecar_symlinks_are_rejected(tmp_path):
    batch = tmp_path / "batch"
    generate_batch(1, 13, batch)
    link = batch / "paired_render.json"
    link.symlink_to(tmp_path / "missing.json")
    with pytest.raises(BatchValidationError):
        validate_batch(batch)
    link.unlink()
    external = tmp_path / "external.json"
    external.write_text("{}")
    link.symlink_to(external)
    with pytest.raises(BatchValidationError):
        validate_batch(batch)
