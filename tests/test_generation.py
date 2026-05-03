from __future__ import annotations

import json
import unicodedata
from pathlib import Path, PurePosixPath

import jsonschema
import pytest
from PIL import Image, ImageDraw

import hocrsyngen.generator as generator_module
from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.generator import (
    CANVAS_SIZE,
    _font_path,
    _load_font,
    _pillow_has_raqm,
    _draw_rtl_text,
    _rtl_display_text,
    _select_font,
    _wrap_hebrew_text,
    generate_batch,
    generate_documents,
    write_manifest,
)
from hocrsyngen.manifest import TextMetadata


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hocrsyngen"
    / "schemas"
    / "generation_manifest.schema.json"
)
HEBREW_CONTRACT_LINE = "אבגד ךםןףץ תיק 42/7: סוף, כסף, דרך, נייר."
SPARSE_NIQQUD_CONTRACT_LINE = unicodedata.normalize(
    "NFC", "בְּדִיקָה קצרה: סעיף 3, עמוד 12."
)
HEBREW_CONTRACT_LINES = [HEBREW_CONTRACT_LINE, SPARSE_NIQQUD_CONTRACT_LINE]


def _load_manifest(output_dir: Path) -> dict:
    return json.loads(
        (output_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )


def _image_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    return list(image.getdata())


def _write_contract_corpus(path: Path, lines: list[str] | None = None) -> Path:
    contract_lines = HEBREW_CONTRACT_LINES if lines is None else lines
    path.write_text("\n".join(contract_lines) + "\n", encoding="utf-8")
    return path


def _assert_logical_hebrew_contract(text: str) -> None:
    assert HEBREW_CONTRACT_LINE in text
    assert SPARSE_NIQQUD_CONTRACT_LINE in text
    assert HEBREW_CONTRACT_LINE[::-1] not in text
    assert SPARSE_NIQQUD_CONTRACT_LINE[::-1] not in text
    assert text == unicodedata.normalize("NFC", text)
    assert all(letter in text for letter in "ךםןףץ")
    assert "42/7:" in text
    assert "סוף, כסף, דרך, נייר." in text
    assert any("\u0591" <= character <= "\u05c7" for character in text)


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
    assert {
        sample["provenance"]["template_id"]: sample["provenance"]["font_id"]
        for sample in first["samples"]
    } == {
        "printed_letter": "alef-regular",
        "handwritten_note": "gveret-levin-regular",
    }


def test_count_zero_emits_empty_manifest(tmp_path: Path) -> None:
    output_dir = tmp_path / "empty"
    payload = generate_batch(count=0, seed=17, output_dir=output_dir).to_dict()

    assert payload["samples"] == []
    assert _load_manifest(output_dir)["samples"] == []


def test_manifest_text_preserves_hebrew_logical_order_rtl_metadata(
    tmp_path: Path,
) -> None:
    payload = generate_batch(count=1, seed=17, output_dir=tmp_path).to_dict()
    sample = payload["samples"][0]
    text = sample["text"]

    assert text["script"] == "Hebr"
    assert text["language"] == "he"
    assert text["direction"] == "rtl"
    assert text["unicode_normalization"] == "NFC"
    assert text["logical_order"] == unicodedata.normalize("NFC", text["logical_order"])
    assert _rtl_display_text("סימן 12") == "סימן 12"


def test_generated_manifest_preserves_logical_order_hebrew_contract_cases(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "contract-batch"
    corpus_path = _write_contract_corpus(tmp_path / "contract_corpus.txt")
    manifest = generator_module.generate_manifest(
        count=1,
        seed=101,
        output_dir=output_dir,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=corpus_path,
    )
    manifest_path = write_manifest(manifest, output_dir)
    raw_manifest = manifest_path.read_text(encoding="utf-8")
    payload = json.loads(raw_manifest)

    assert HEBREW_CONTRACT_LINE in raw_manifest
    assert SPARSE_NIQQUD_CONTRACT_LINE in raw_manifest
    assert "\\u05" not in raw_manifest

    sample = payload["samples"][0]
    text = sample["text"]["logical_order"]
    lines = text.splitlines()

    assert lines[0] == "מכתב מנהלי"
    assert lines[1:3] == HEBREW_CONTRACT_LINES
    assert len(lines) == 4
    assert sample["text"] == {
        "logical_order": text,
        "script": "Hebr",
        "language": "he",
        "direction": "rtl",
        "unicode_normalization": "NFC",
    }
    _assert_logical_hebrew_contract(text)


def test_draw_rtl_text_passes_logical_text_to_pillow_with_rtl_direction() -> None:
    class RecordingDraw:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def text(self, xy, text, **kwargs) -> None:
            self.calls.append({"xy": xy, "text": text, **kwargs})

    draw = RecordingDraw()
    font = object()

    _draw_rtl_text(
        draw, (500, 40), HEBREW_CONTRACT_LINE, font=font, fill=(1, 2, 3), anchor="ra"
    )

    assert draw.calls == [
        {
            "xy": (500, 40),
            "text": HEBREW_CONTRACT_LINE,
            "font": font,
            "fill": (1, 2, 3),
            "anchor": "ra",
            "direction": "rtl",
        }
    ]
    assert _rtl_display_text(HEBREW_CONTRACT_LINE) == HEBREW_CONTRACT_LINE


def test_renderer_smoke_outputs_asset_for_hebrew_contract_cases_without_mutating_manifest_text(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "rendered-contract"
    corpus_path = _write_contract_corpus(tmp_path / "contract_corpus.txt")
    documents = generate_documents(
        count=1,
        seed=101,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=corpus_path,
        output_dir=output_dir,
    )

    document = documents[0]
    assert document.logical_text.splitlines()[1:3] == HEBREW_CONTRACT_LINES
    _assert_logical_hebrew_contract(document.logical_text)
    with Image.open(document.path) as opened:
        image = opened.convert("RGB")
        assert image.size == CANVAS_SIZE
        rendered_region = image.crop((140, 250, 1060, 760))
        dark_ink_pixels = sum(
            1
            for r, g, b in _image_pixels(rendered_region)
            if r < 115 and g < 105 and b < 95
        )
        assert dark_ink_pixels > 5_000


def test_text_corpus_covers_final_letters_numerals_punctuation_and_sparse_niqqud() -> (
    None
):
    corpus = default_text_corpus_path().read_text(encoding="utf-8")

    assert all(letter in corpus for letter in "ךםןףץ")
    assert any(character.isdigit() for character in corpus)
    assert any(character in corpus for character in ":,./")
    assert any("\u0591" <= character <= "\u05c7" for character in corpus)


def test_synthetic_generation_uses_packaged_fonts_and_curated_text(
    tmp_path: Path,
) -> None:
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
    assert {document.template_id: document.font_id for document in documents} == {
        "printed_letter": "alef-regular",
        "handwritten_note": "gveret-levin-regular",
    }
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
        red_stamp_pixels = sum(
            1 for r, g, b in printed_pixels if r > 90 and r > g * 1.45 and r > b * 1.45
        )
        dark_ink_pixels = sum(
            1 for r, g, b in printed_pixels if r < 115 and g < 105 and b < 95
        )
        assert red_stamp_pixels > 500
        assert dark_ink_pixels > 5_000

    with Image.open(by_template["handwritten_note"].path).convert("RGB") as handwritten:
        marginalia_region = handwritten.crop((120, 430, 280, 760))
        marginalia_pixels = _image_pixels(marginalia_region)
        marginalia_ink_pixels = sum(
            1 for r, g, b in marginalia_pixels if r < 115 and g < 105 and b < 95
        )
        assert marginalia_ink_pixels > 150


def test_synthetic_generation_rejects_invalid_inputs(tmp_path: Path) -> None:
    invalid_template_output = tmp_path / "invalid-template"
    with pytest.raises(
        ValueError, match="Unsupported synthetic template_id: typo_template"
    ):
        generate_documents(
            count=1,
            seed=7,
            template_ids=["typo_template"],
            font_manifest_path=default_font_manifest_path(),
            text_corpus_path=default_text_corpus_path(),
            output_dir=invalid_template_output,
        )
    assert not invalid_template_output.exists()

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

    missing_font_manifest_path = tmp_path / "missing_font_manifest.yaml"
    missing_font_output = tmp_path / "missing-font-output"
    missing_font_manifest_path.write_text(
        "fonts:\n  - id: alef-regular\n    file: missing.ttf\n    style: printed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Synthetic font file is missing"):
        generate_documents(
            count=1,
            seed=7,
            template_ids=["printed_letter"],
            font_manifest_path=missing_font_manifest_path,
            text_corpus_path=text_corpus_path,
            output_dir=missing_font_output,
        )
    assert not missing_font_output.exists()

    invalid_font_manifest_path = tmp_path / "invalid_font_manifest.yaml"
    invalid_font_output = tmp_path / "invalid-font-output"
    (tmp_path / "invalid.ttf").write_bytes(b"not a font")
    invalid_font_manifest_path.write_text(
        "fonts:\n  - id: alef-regular\n    file: invalid.ttf\n    style: printed\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError, match="Synthetic font file is invalid or unreadable"
    ):
        generate_documents(
            count=1,
            seed=7,
            template_ids=["printed_letter"],
            font_manifest_path=invalid_font_manifest_path,
            text_corpus_path=text_corpus_path,
            output_dir=invalid_font_output,
        )
    assert not invalid_font_output.exists()

    with pytest.raises(ValueError, match="seed must be non-negative"):
        generate_batch(count=1, seed=-1, output_dir=tmp_path / "negative-seed")
    assert not (tmp_path / "negative-seed").exists()

    with pytest.raises(ValueError, match="requires at least one template_id"):
        generate_batch(
            count=1, seed=7, output_dir=tmp_path / "empty-templates", template_ids=[]
        )
    assert not (tmp_path / "empty-templates").exists()

    file_output = tmp_path / "file-output"
    file_output.write_text("existing file\n", encoding="utf-8")
    with pytest.raises(ValueError, match="output path exists and is not a directory"):
        generate_batch(count=1, seed=7, output_dir=file_output)
    assert file_output.read_text(encoding="utf-8") == "existing file\n"


def test_schema_rejects_backslash_asset_paths(tmp_path: Path) -> None:
    payload = generate_batch(count=1, seed=17, output_dir=tmp_path).to_dict()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload["samples"][0]["pages"][0]["asset_path"] = "..\\page.jpg"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_text_metadata_rejects_empty_or_non_nfc_logical_order() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        TextMetadata(logical_order="")

    with pytest.raises(ValueError, match="NFC-normalized"):
        TextMetadata(logical_order="\ufb31")


def test_font_path_wrapping_and_font_selection_helpers(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("fonts: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing a file reference"):
        _font_path(manifest_path, {"id": "broken-font"})
    with pytest.raises(ValueError, match="Synthetic font file is missing"):
        _font_path(manifest_path, {"id": "broken-font", "file": "missing.ttf"})
    with pytest.raises(ValueError, match="flat relative filename"):
        _font_path(manifest_path, {"id": "broken-font", "file": "../escape.ttf"})
    with pytest.raises(ValueError, match="flat relative filename"):
        _font_path(manifest_path, {"id": "broken-font", "file": "nested/font.ttf"})
    with pytest.raises(ValueError, match="flat relative filename"):
        _font_path(manifest_path, {"id": "broken-font", "file": "nested\\font.ttf"})
    assert _select_font(
        [{"id": "alef-regular", "style": "printed"}], "printed_letter"
    ) == {
        "id": "alef-regular",
        "style": "printed",
    }
    with pytest.raises(ValueError, match="has style 'handwritten_like'"):
        _select_font(
            [{"id": "alef-regular", "style": "handwritten_like"}],
            "printed_letter",
        )
    assert _select_font(
        [{"id": "gveret-levin-regular", "style": "handwritten_like"}], "handwritten_note"
    ) == {
        "id": "gveret-levin-regular",
        "style": "handwritten_like",
    }
    with pytest.raises(ValueError, match="has style 'printed'"):
        _select_font(
            [{"id": "gveret-levin-regular", "style": "printed"}],
            "handwritten_note",
        )
    with pytest.raises(ValueError, match="No synthetic font registered"):
        _select_font([{"id": "alef-regular", "style": "printed"}], "handwritten_note")

    image = Image.new("RGB", (600, 400), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _load_font(
        _font_path(
            default_font_manifest_path(),
            {"id": "alef-regular", "file": "Alef-Regular.ttf"},
        ),
        42,
    )
    assert _wrap_hebrew_text(draw, "", font, max_width=200) == [""]
    assert (
        len(
            _wrap_hebrew_text(
                draw, "מכתב מנהלי רישום ארכיוני הודעה פנימית", font, max_width=100
            )
        )
        > 1
    )


def test_generation_requires_raqm_for_hebrew_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _pillow_has_raqm.cache_clear()
    monkeypatch.setattr(
        generator_module.features,
        "check",
        lambda feature: False if feature == "raqm" else True,
    )

    with pytest.raises(RuntimeError, match="requires Pillow with libraqm support"):
        generate_batch(count=1, seed=17, output_dir=tmp_path)

    _pillow_has_raqm.cache_clear()


def test_no_hocrgen_network_or_gpu_baseline_dependencies() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project_root / "src" / "hocrsyngen").glob("*.py")
    )
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "import hocrgen" not in source
    assert "from hocrgen" not in source
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "torch" not in pyproject
    assert "tensorflow" not in pyproject
    assert "diffusers" not in pyproject
