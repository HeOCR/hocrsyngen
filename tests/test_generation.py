from __future__ import annotations

import json
import unicodedata
from pathlib import Path, PurePosixPath

import jsonschema
import pytest
from PIL import Image, ImageDraw

from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.generator import (
    CANVAS_SIZE,
    _font_path,
    _load_font,
    _rtl_display_text,
    _select_font,
    _wrap_hebrew_text,
    generate_batch,
    generate_documents,
)


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hocrsyngen"
    / "schemas"
    / "generation_manifest.schema.json"
)


def _load_manifest(output_dir: Path) -> dict:
    return json.loads((output_dir / "generation_manifest.json").read_text(encoding="utf-8"))


def _image_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    return list(image.getdata())


def test_cli_manifest_contract_schema_and_relative_assets(tmp_path: Path) -> None:
    output_dir = tmp_path / "fixture-batch"
    manifest = generate_batch(count=2, seed=17, output_dir=output_dir)
    payload = _load_manifest(output_dir)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    jsonschema.validate(payload, schema)

    assert payload == manifest.to_dict()
    assert payload["manifest_version"] == "1.0"
    assert payload["license"] == "PROJECT-SYNTHETIC"
    assert [sample["sample_id"] for sample in payload["samples"]] == [
        "hocrsyngen-s00000017-000000",
        "hocrsyngen-s00000017-000001",
    ]
    for sample in payload["samples"]:
        page = sample["pages"][0]
        asset_path = PurePosixPath(page["asset_path"])
        assert not asset_path.is_absolute()
        assert ".." not in asset_path.parts
        assert (output_dir / page["asset_path"]).is_file()
        with Image.open(output_dir / page["asset_path"]) as image:
            assert image.size == CANVAS_SIZE
            assert image.mode == "RGB"


def test_generation_is_deterministic_for_fixed_seed(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = generate_batch(count=2, seed=23, output_dir=first_dir).to_dict()
    second = generate_batch(count=2, seed=23, output_dir=second_dir).to_dict()

    assert first == second
    assert [sample["pages"][0]["sha256"] for sample in first["samples"]] == [
        sample["pages"][0]["sha256"] for sample in second["samples"]
    ]
    assert first["samples"][0]["recipe_id"] != first["samples"][1]["recipe_id"]


def test_manifest_text_preserves_hebrew_logical_order_rtl_metadata(tmp_path: Path) -> None:
    payload = generate_batch(count=1, seed=17, output_dir=tmp_path).to_dict()
    sample = payload["samples"][0]
    text = sample["text"]

    assert text["script"] == "Hebr"
    assert text["language"] == "he"
    assert text["direction"] == "rtl"
    assert text["unicode_normalization"] == "NFC"
    assert text["logical_order"] == unicodedata.normalize("NFC", text["logical_order"])
    assert _rtl_display_text("סימן 12") == "סימן 12"


def test_text_corpus_covers_final_letters_numerals_punctuation_and_sparse_niqqud() -> None:
    corpus = default_text_corpus_path().read_text(encoding="utf-8")

    assert any(letter in corpus for letter in "ךםןףץ")
    assert any(character.isdigit() for character in corpus)
    assert any(character in corpus for character in ":,./")
    assert any("\u0591" <= character <= "\u05c7" for character in corpus)


def test_synthetic_generation_uses_packaged_fonts_and_curated_text(tmp_path: Path) -> None:
    documents = generate_documents(
        count=2,
        seed=11,
        template_ids=["printed_letter", "handwritten_note"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / "synthetic",
    )

    assert {document.path.suffix for document in documents} == {".jpg"}
    assert {document.generator_version for document in documents} == {"d4a-realism-v2"}
    assert {document.font_id for document in documents} == {"gveret-levin-regular"}
    assert {document.recipe_id for document in documents} == {
        "printed_letter_form_v1",
        "handwritten_note_marginalia_v1",
    }
    for document in documents:
        assert document.path.is_file()
        assert not PurePosixPath(document.asset_path).is_absolute()


def test_synthetic_visual_recipes_render_expected_page_features(tmp_path: Path) -> None:
    documents = generate_documents(
        count=2,
        seed=31,
        template_ids=["printed_letter", "handwritten_note"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / "synthetic",
    )
    by_template = {document.template_id: document for document in documents}

    with Image.open(by_template["printed_letter"].path).convert("RGB") as printed:
        form_region = printed.crop((140, 330, 1060, 820))
        printed_pixels = _image_pixels(form_region)
        red_stamp_pixels = sum(1 for r, g, b in printed_pixels if r > 90 and r > g * 1.45 and r > b * 1.45)
        dark_ink_pixels = sum(1 for r, g, b in printed_pixels if r < 115 and g < 105 and b < 95)
        assert red_stamp_pixels > 500
        assert dark_ink_pixels > 5_000

    with Image.open(by_template["handwritten_note"].path).convert("RGB") as handwritten:
        marginalia_region = handwritten.crop((120, 430, 280, 760))
        marginalia_pixels = _image_pixels(marginalia_region)
        marginalia_ink_pixels = sum(1 for r, g, b in marginalia_pixels if r < 115 and g < 105 and b < 95)
        assert marginalia_ink_pixels > 150


def test_synthetic_generation_rejects_invalid_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported synthetic template_id: typo_template"):
        generate_documents(
            count=1,
            seed=7,
            template_ids=["typo_template"],
            font_manifest_path=default_font_manifest_path(),
            text_corpus_path=default_text_corpus_path(),
            output_dir=tmp_path / "synthetic",
        )

    font_manifest_path = tmp_path / "fonts.yaml"
    text_corpus_path = tmp_path / "corpus.txt"
    font_manifest_path.write_text("not_fonts: []\n", encoding="utf-8")
    text_corpus_path.write_text("שורה ארכיונית תקינה\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing a valid 'fonts' list"):
        generate_documents(
            count=1,
            seed=7,
            template_ids=["printed_letter"],
            font_manifest_path=font_manifest_path,
            text_corpus_path=text_corpus_path,
            output_dir=tmp_path / "out",
        )

    with pytest.raises(ValueError, match="seed must be non-negative"):
        generate_batch(count=1, seed=-1, output_dir=tmp_path / "negative-seed")

    with pytest.raises(ValueError, match="requires at least one template_id"):
        generate_batch(count=1, seed=7, output_dir=tmp_path / "empty-templates", template_ids=[])


def test_schema_rejects_backslash_asset_paths(tmp_path: Path) -> None:
    payload = generate_batch(count=1, seed=17, output_dir=tmp_path).to_dict()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload["samples"][0]["pages"][0]["asset_path"] = "..\\page.jpg"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_font_path_wrapping_and_font_selection_helpers(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("fonts: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing a file reference"):
        _font_path(manifest_path, {"id": "broken-font"})
    with pytest.raises(ValueError, match="Synthetic font file is missing"):
        _font_path(manifest_path, {"id": "broken-font", "file": "missing.ttf"})
    with pytest.raises(ValueError, match="No synthetic font registered"):
        _select_font([{"id": "alef-regular", "style": "printed"}], "printed_letter")

    image = Image.new("RGB", (600, 400), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _load_font(_font_path(default_font_manifest_path(), {"id": "alef-regular", "file": "Alef-Regular.ttf"}), 42)
    assert _wrap_hebrew_text(draw, "", font, max_width=200) == [""]
    assert len(_wrap_hebrew_text(draw, "מכתב מנהלי רישום ארכיוני הודעה פנימית", font, max_width=100)) > 1


def test_no_hocrgen_network_or_gpu_baseline_dependencies() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = "\n".join(path.read_text(encoding="utf-8") for path in (project_root / "src" / "hocrsyngen").glob("*.py"))
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "import hocrgen" not in source
    assert "from hocrgen" not in source
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "torch" not in pyproject
    assert "tensorflow" not in pyproject
    assert "diffusers" not in pyproject
