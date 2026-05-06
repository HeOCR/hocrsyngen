from __future__ import annotations

import json
import unicodedata
from pathlib import Path, PurePosixPath

import jsonschema
import pytest
from PIL import Image, ImageChops, ImageDraw, ImageFilter, features

import hocrsyngen.generator as generator_module
from hocrsyngen.assets import default_font_manifest_path, default_text_corpus_path
from hocrsyngen.generator import (
    CANVAS_SIZE,
    _degradation_preset,
    _font_path,
    load_font_manifest,
    _load_font,
    _pillow_has_raqm,
    _draw_rtl_text,
    _require_raqm,
    _rtl_display_text,
    _select_font,
    _wrap_hebrew_text,
    generate_batch,
    generate_documents,
    template_catalog,
    write_manifest,
)
from hocrsyngen.io import sha256_file
from hocrsyngen.manifest import TextMetadata


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "hocrsyngen"
    / "schemas"
    / "generation_manifest.schema.json"
)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
EDGE_TEXT_CORPUS_PATH = FIXTURES_DIR / "hebrew_edge_text_corpus.txt"
BIDI_NIQQUD_CORPUS_PATH = FIXTURES_DIR / "bidi_niqqud_rendering_corpus.txt"
EDGE_TEXT_CORPUS_NOTES_PATH = FIXTURES_DIR / "README.md"
HEBREW_CONTRACT_LINE = "אבגד ךםןףץ תיק 42/7: סוף, כסף, דרך, נייר."
SPARSE_NIQQUD_CONTRACT_LINE = unicodedata.normalize("NFC", "בְּדִיקָה קצרה: סעיף 3, עמוד 12.")
HEBREW_CONTRACT_LINES = [HEBREW_CONTRACT_LINE, SPARSE_NIQQUD_CONTRACT_LINE]
HEBREW_EDGE_TEXT_LINES = [
    "בדיקת סופיות: מלך, חכם, ענן, סוף, ציץ.",
    "תאריך 03/12/1924 נרשם לצד סכום 1,250.75.",
    "מזהה תיק HEOCR-2026-אבג-42 נמסר באישור מס' 7.",
    "קטע Latin קצר: archive ref ABC-17b בתוך משפט עברי.",
]
HEBREW_EDGE_TEXT_MARKERS = {
    "final_forms": ["מלך", "חכם", "ענן", "סוף", "ציץ"],
    "numerals": ["03", "12", "1924", "1,250.75", "7"],
    "punctuation": [":", ",", ".", "/", "-", "'"],
    "dates": ["03/12/1924"],
    "identifiers": ["HEOCR-2026-אבג-42", "ABC-17b"],
    "latin_fragments": ["Latin", "archive", "ref", "ABC"],
}
HEBREW_EDGE_TEXT_COVERAGE_TERMS = [
    "final forms",
    "numerals",
    "punctuation",
    "dates",
    "identifiers",
    "Latin fragments",
]
BIDI_NIQQUD_LINES = [
    unicodedata.normalize("NFC", "נִקּוּד דל: בְּדִיקָה קצרה לְתִיק 42/7."),
    unicodedata.normalize("NFC", "נִקּוּד מלא: הַיְּלָדִים כָּתְבוּ בַּמַּחְבֶּרֶת."),
    "כיוון מעורב: תיק HEOCR-2026-A17 נבדק בשעה 08:30.",
    'סימני פיסוק: "שלום", אמרה רחל; האם נרשם מס\' 5?',
]
BIDI_NIQQUD_SEED_2027_BODY_LINES = [
    BIDI_NIQQUD_LINES[0],
    BIDI_NIQQUD_LINES[1],
    BIDI_NIQQUD_LINES[3],
    BIDI_NIQQUD_LINES[2],
]
BIDI_NIQQUD_MARKERS = {
    "sparse_niqqud": [
        unicodedata.normalize("NFC", "נִקּוּד דל"),
        unicodedata.normalize("NFC", "בְּדִיקָה"),
        unicodedata.normalize("NFC", "לְתִיק"),
    ],
    "fuller_niqqud": [
        unicodedata.normalize("NFC", "הַיְּלָדִים"),
        unicodedata.normalize("NFC", "כָּתְבוּ"),
        unicodedata.normalize("NFC", "בַּמַּחְבֶּרֶת"),
    ],
    "latin_fragments": ["HEOCR", "A17"],
    "numeric_fragments": ["2026", "42/7", "08:30", "5"],
    "punctuation": [":", ".", "-", "/", '"', ";", "'", "?"],
}
FONT_SHAPING_AUDIT_LINES = [
    HEBREW_CONTRACT_LINE,
    SPARSE_NIQQUD_CONTRACT_LINE,
    BIDI_NIQQUD_LINES[1],
    BIDI_NIQQUD_LINES[2],
    BIDI_NIQQUD_LINES[3],
]
PACKAGED_FONT_AUDIT_CASES = [
    ("printed_letter", 42),
    ("handwritten_note", 46),
    ("archive_card", 42),
]
DEGRADATION_VARIANT_CASES = [
    (
        "printed_letter",
        "printed_letter_heavy_scan",
        "printed_letter_form_heavy_scan_v1",
        "office_scan_heavy",
        "alef-regular",
    ),
    (
        "handwritten_note",
        "handwritten_note_heavy_wear",
        "handwritten_note_marginalia_heavy_wear_v1",
        "notebook_scan_heavy_wear",
        "gveret-levin-regular",
    ),
    (
        "archive_card",
        "archive_card_faded_scan",
        "archive_card_identifier_faded_scan_v1",
        "archive_scan_faded",
        "alef-regular",
    ),
]


def _load_manifest(output_dir: Path) -> dict:
    return json.loads((output_dir / "generation_manifest.json").read_text(encoding="utf-8"))


def _image_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    return list(image.getdata())


def _changed_pixel_count(first: Image.Image, second: Image.Image) -> int:
    return sum(
        1
        for pixel in _image_pixels(ImageChops.difference(first, second))
        if pixel != (0, 0, 0)
    )


def _mean_luminance(image: Image.Image) -> float:
    pixels = _image_pixels(image)
    return sum(r + g + b for r, g, b in pixels) / (3 * len(pixels))


def _mean_edge_strength(image: Image.Image) -> float:
    edge_image = image.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_pixels = list(edge_image.getdata())
    return sum(edge_pixels) / len(edge_pixels)


def _dark_ink_pixel_count(image: Image.Image) -> int:
    return sum(1 for r, g, b in _image_pixels(image) if r < 115 and g < 105 and b < 95)


def _red_stamp_pixel_count(image: Image.Image) -> int:
    return sum(1 for r, g, b in _image_pixels(image) if r > 90 and r > g * 1.45 and r > b * 1.45)


def _ruled_pixel_count(image: Image.Image) -> int:
    return sum(
        1
        for r, g, b in _image_pixels(image)
        if 145 <= r <= 225 and 135 <= g <= 215 and 115 <= b <= 200
    )


def _write_contract_corpus(path: Path, lines: list[str] | None = None) -> Path:
    contract_lines = HEBREW_CONTRACT_LINES if lines is None else lines
    path.write_text("\n".join(contract_lines) + "\n", encoding="utf-8")
    return path


def _assert_hebrew_edge_text_markers(text: str) -> None:
    for markers in HEBREW_EDGE_TEXT_MARKERS.values():
        for marker in markers:
            assert marker in text
    assert all(letter in text for letter in "ךםןףץ")
    assert text == unicodedata.normalize("NFC", text)


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


def _assert_bidi_niqqud_markers(text: str) -> None:
    for markers in BIDI_NIQQUD_MARKERS.values():
        for marker in markers:
            assert marker in text
    assert text == unicodedata.normalize("NFC", text)
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


def test_stable_seed_manifest_identity_and_output_layout_drift_guard(tmp_path: Path) -> None:
    output_dir = tmp_path / "stable-seed"
    payload = generate_batch(count=4, seed=29, output_dir=output_dir).to_dict()

    assert sorted(path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*")) == [
        "assets",
        "assets/hocrsyngen-s00000029-000000",
        "assets/hocrsyngen-s00000029-000000/page_0001.jpg",
        "assets/hocrsyngen-s00000029-000001",
        "assets/hocrsyngen-s00000029-000001/page_0001.jpg",
        "assets/hocrsyngen-s00000029-000002",
        "assets/hocrsyngen-s00000029-000002/page_0001.jpg",
        "assets/hocrsyngen-s00000029-000003",
        "assets/hocrsyngen-s00000029-000003/page_0001.jpg",
        "generation_manifest.json",
    ]
    assert _load_manifest(output_dir) == payload
    assert payload["manifest_version"] == "1.0"
    assert payload["generator_name"] == "hocrsyngen"
    assert payload["license"] == "PROJECT-SYNTHETIC"
    assert [sample["sample_id"] for sample in payload["samples"]] == [
        "hocrsyngen-s00000029-000000",
        "hocrsyngen-s00000029-000001",
        "hocrsyngen-s00000029-000002",
        "hocrsyngen-s00000029-000003",
    ]

    expected_stable_projection = [
        {
            "sample_id": "hocrsyngen-s00000029-000000",
            "page_id": "hocrsyngen-s00000029-000000-page-0001",
            "asset_path": "assets/hocrsyngen-s00000029-000000/page_0001.jpg",
            "recipe_id": "printed_letter_form_v1",
            "template_id": "printed_letter",
            "degradation_preset": "office_scan_soft",
            "font_id": "alef-regular",
            "sample_index": 0,
            "title": "מכתב מנהלי",
        },
        {
            "sample_id": "hocrsyngen-s00000029-000001",
            "page_id": "hocrsyngen-s00000029-000001-page-0001",
            "asset_path": "assets/hocrsyngen-s00000029-000001/page_0001.jpg",
            "recipe_id": "handwritten_note_marginalia_v1",
            "template_id": "handwritten_note",
            "degradation_preset": "notebook_scan_worn",
            "font_id": "gveret-levin-regular",
            "sample_index": 1,
            "title": "רישום קצר",
        },
        {
            "sample_id": "hocrsyngen-s00000029-000002",
            "page_id": "hocrsyngen-s00000029-000002-page-0001",
            "asset_path": "assets/hocrsyngen-s00000029-000002/page_0001.jpg",
            "recipe_id": "printed_letter_form_v1",
            "template_id": "printed_letter",
            "degradation_preset": "office_scan_soft",
            "font_id": "alef-regular",
            "sample_index": 2,
            "title": "רישום ארכיוני",
        },
        {
            "sample_id": "hocrsyngen-s00000029-000003",
            "page_id": "hocrsyngen-s00000029-000003-page-0001",
            "asset_path": "assets/hocrsyngen-s00000029-000003/page_0001.jpg",
            "recipe_id": "handwritten_note_marginalia_v1",
            "template_id": "handwritten_note",
            "degradation_preset": "notebook_scan_worn",
            "font_id": "gveret-levin-regular",
            "sample_index": 3,
            "title": "פנקס הערות",
        },
    ]

    stable_projection = []
    for sample in payload["samples"]:
        [page] = sample["pages"]
        asset_path = PurePosixPath(page["asset_path"])
        stable_projection.append(
            {
                "sample_id": sample["sample_id"],
                "page_id": page["page_id"],
                "asset_path": page["asset_path"],
                "recipe_id": sample["recipe_id"],
                "template_id": sample["provenance"]["template_id"],
                "degradation_preset": sample["provenance"]["degradation_preset"],
                "font_id": sample["provenance"]["font_id"],
                "sample_index": sample["provenance"]["sample_index"],
                "title": sample["text"]["logical_order"].splitlines()[0],
            }
        )

        assert not asset_path.is_absolute()
        assert ".." not in asset_path.parts
        assert "\\" not in page["asset_path"]
        assert page["media_type"] == "image/jpeg"
        assert (page["width"], page["height"]) == CANVAS_SIZE
        assert (output_dir / Path(*asset_path.parts)).is_file()
        assert sample["generator_version"] == "d4a-realism-v2"
        assert sample["provenance"]["seed"] == 29
        assert sample["provenance"]["recipe_id"] == sample["recipe_id"]
        assert sample["provenance"]["source_corpus"] == "packaged:synthetic/texts/hebrew_lines.txt"
        assert sample["controls"] == {"persona": None, "condition": None}
        assert sample["license"] == "PROJECT-SYNTHETIC"
        assert sample["text"]["script"] == "Hebr"
        assert sample["text"]["language"] == "he"
        assert sample["text"]["direction"] == "rtl"
        assert sample["text"]["unicode_normalization"] == "NFC"
        assert sample["text"]["logical_order"] == unicodedata.normalize(
            "NFC", sample["text"]["logical_order"]
        )

    assert stable_projection == expected_stable_projection


def test_stable_seed_page_hashes_track_assets_and_seed_changes(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    changed_seed_dir = tmp_path / "changed-seed"
    first = generate_batch(count=3, seed=29, output_dir=first_dir).to_dict()
    second = generate_batch(count=3, seed=29, output_dir=second_dir).to_dict()
    changed_seed = generate_batch(count=3, seed=30, output_dir=changed_seed_dir).to_dict()

    first_hashes = [sample["pages"][0]["sha256"] for sample in first["samples"]]
    second_hashes = [sample["pages"][0]["sha256"] for sample in second["samples"]]
    changed_seed_hashes = [
        sample["pages"][0]["sha256"] for sample in changed_seed["samples"]
    ]

    assert first_hashes == second_hashes
    assert all(
        first_hash != changed_seed_hash
        for first_hash, changed_seed_hash in zip(
            first_hashes, changed_seed_hashes, strict=True
        )
    )
    assert len(set(first_hashes)) == len(first_hashes)
    for batch_dir, payload in [
        (first_dir, first),
        (second_dir, second),
        (changed_seed_dir, changed_seed),
    ]:
        for sample in payload["samples"]:
            page = sample["pages"][0]
            assert len(page["sha256"]) == 64
            assert set(page["sha256"]) <= set("0123456789abcdef")
            assert page["sha256"] == sha256_file(batch_dir / page["asset_path"])


def test_count_zero_emits_empty_manifest(tmp_path: Path) -> None:
    output_dir = tmp_path / "empty"
    payload = generate_batch(count=0, seed=17, output_dir=output_dir).to_dict()

    assert payload["samples"] == []
    assert _load_manifest(output_dir)["samples"] == []


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


def test_generated_manifest_preserves_logical_order_hebrew_contract_cases(tmp_path: Path) -> None:
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

    _draw_rtl_text(draw, (500, 40), HEBREW_CONTRACT_LINE, font=font, fill=(1, 2, 3), anchor="ra")

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


def test_renderer_smoke_outputs_asset_for_hebrew_contract_cases_without_mutating_manifest_text(tmp_path: Path) -> None:
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
        dark_ink_pixels = sum(1 for r, g, b in _image_pixels(rendered_region) if r < 115 and g < 105 and b < 95)
        assert dark_ink_pixels > 5_000


def test_text_corpus_covers_final_letters_numerals_punctuation_and_sparse_niqqud() -> None:
    corpus = default_text_corpus_path().read_text(encoding="utf-8")

    assert all(letter in corpus for letter in "ךםןףץ")
    assert any(character.isdigit() for character in corpus)
    assert any(character in corpus for character in ":,./")
    assert any("\u0591" <= character <= "\u05c7" for character in corpus)


def test_hebrew_edge_text_corpus_fixture_is_curated_and_nfc() -> None:
    corpus_lines = generator_module.load_text_corpus(EDGE_TEXT_CORPUS_PATH)
    provenance_notes = EDGE_TEXT_CORPUS_NOTES_PATH.read_text(encoding="utf-8")
    corpus_text = "\n".join(corpus_lines)

    assert corpus_lines == HEBREW_EDGE_TEXT_LINES
    assert all(line == unicodedata.normalize("NFC", line) for line in corpus_lines)
    assert "Synthetic project-authored Hebrew edge text corpus" in provenance_notes
    assert "not real-source text" in provenance_notes
    assert all(term in provenance_notes for term in HEBREW_EDGE_TEXT_COVERAGE_TERMS)
    _assert_hebrew_edge_text_markers(corpus_text)


def test_generated_document_preserves_hebrew_edge_text_corpus_logical_order(tmp_path: Path) -> None:
    output_dir = tmp_path / "edge-text-batch"
    documents = generate_documents(
        count=1,
        seed=2026,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=EDGE_TEXT_CORPUS_PATH,
        output_dir=output_dir,
    )

    document = documents[0]
    text = document.logical_text
    lines = text.splitlines()

    assert document.title == "מכתב מנהלי"
    assert document.footer == "עמוד 91"
    assert lines[0] == "מכתב מנהלי"
    assert set(lines[1:5]) == set(HEBREW_EDGE_TEXT_LINES)
    assert len(lines) == 6
    assert lines[-1] == "עמוד 91"
    _assert_hebrew_edge_text_markers(text)


def test_bidi_niqqud_rendering_corpus_fixture_is_curated_and_nfc() -> None:
    corpus_lines = generator_module.load_text_corpus(BIDI_NIQQUD_CORPUS_PATH)
    provenance_notes = EDGE_TEXT_CORPUS_NOTES_PATH.read_text(encoding="utf-8")
    corpus_text = "\n".join(corpus_lines)

    assert corpus_lines == BIDI_NIQQUD_LINES
    assert all(line == unicodedata.normalize("NFC", line) for line in corpus_lines)
    assert "`bidi_niqqud_rendering_corpus.txt`" in provenance_notes
    assert "Synthetic project-authored Hebrew bidi and niqqud rendering corpus" in provenance_notes
    assert "not real-source text" in provenance_notes
    _assert_bidi_niqqud_markers(corpus_text)


def test_generated_document_preserves_bidi_niqqud_corpus_logical_order(tmp_path: Path) -> None:
    output_dir = tmp_path / "bidi-niqqud-batch"
    documents = generate_documents(
        count=1,
        seed=2027,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=BIDI_NIQQUD_CORPUS_PATH,
        output_dir=output_dir,
    )

    document = documents[0]
    text = document.logical_text
    lines = text.splitlines()

    assert document.title == "מכתב מנהלי"
    assert document.footer == "עמוד 53"
    assert lines[0] == "מכתב מנהלי"
    assert lines[1:5] == BIDI_NIQQUD_SEED_2027_BODY_LINES
    assert len(lines) == 6
    assert lines[-1] == "עמוד 53"
    _assert_bidi_niqqud_markers(text)


def test_renderer_routes_bidi_niqqud_lines_through_rtl_text_draw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "routed-bidi-niqqud"
    draw_calls: list[str] = []
    original_draw_rtl_text = generator_module._draw_rtl_text

    def recording_draw_rtl_text(draw, xy, text, **kwargs) -> None:
        draw_calls.append(text)
        original_draw_rtl_text(draw, xy, text, **kwargs)

    monkeypatch.setattr(generator_module, "_draw_rtl_text", recording_draw_rtl_text)

    documents = generate_documents(
        count=1,
        seed=2027,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=BIDI_NIQQUD_CORPUS_PATH,
        output_dir=output_dir,
    )

    routed_bidi_lines = [text for text in draw_calls if text in BIDI_NIQQUD_LINES]
    assert routed_bidi_lines == BIDI_NIQQUD_SEED_2027_BODY_LINES
    assert documents[0].logical_text.splitlines()[1:5] == routed_bidi_lines


def test_renderer_smoke_outputs_asset_for_bidi_niqqud_cases(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered-bidi-niqqud"
    documents = generate_documents(
        count=1,
        seed=2027,
        template_ids=["printed_letter"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=BIDI_NIQQUD_CORPUS_PATH,
        output_dir=output_dir,
    )

    document = documents[0]
    _assert_bidi_niqqud_markers(document.logical_text)
    with Image.open(document.path) as opened:
        image = opened.convert("RGB")
        assert image.size == CANVAS_SIZE
        rendered_region = image.crop((140, 250, 1060, 760))
        dark_ink_pixels = sum(1 for r, g, b in _image_pixels(rendered_region) if r < 115 and g < 105 and b < 95)
        assert dark_ink_pixels > 5_000


@pytest.mark.parametrize(
    ("template_id", "font_size"),
    PACKAGED_FONT_AUDIT_CASES,
)
def test_packaged_fonts_render_hebrew_shaping_audit_cases_through_rtl_path(
    template_id: str,
    font_size: int,
) -> None:
    assert features.check("raqm"), (
        "Pillow libraqm support is required for Hebrew RTL font shaping audit coverage."
    )
    assert _pillow_has_raqm()

    manifest_path = default_font_manifest_path()
    font_manifest = load_font_manifest(manifest_path)
    fonts = font_manifest["fonts"]
    catalog_entry = {entry.template_id: entry for entry in template_catalog()}[template_id]
    font_entry = _select_font(fonts, template_id)
    assert font_entry["id"] == catalog_entry.font_id

    font = _load_font(_font_path(manifest_path, font_entry), font_size)
    image = Image.new("RGB", (1100, 520), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    for index, line in enumerate(FONT_SHAPING_AUDIT_LINES):
        assert line == unicodedata.normalize("NFC", line)
        y = 55 + (index * 82)
        left, top, right, bottom = draw.textbbox((1030, y), line, font=font, anchor="ra", direction="rtl")
        assert right > left
        assert bottom > top
        assert right - left > 100
        assert bottom - top > 10
        _draw_rtl_text(draw, (1030, y), line, font=font, fill=(20, 18, 15), anchor="ra")

    dark_ink_pixels = sum(1 for r, g, b in _image_pixels(image) if r < 80 and g < 80 and b < 80)
    assert dark_ink_pixels > 1_000

    rtl_image = Image.new("RGB", (1100, 180), (255, 255, 255))
    rtl_draw = ImageDraw.Draw(rtl_image)
    _draw_rtl_text(
        rtl_draw,
        (1030, 55),
        BIDI_NIQQUD_LINES[2],
        font=font,
        fill=(20, 18, 15),
        anchor="ra",
    )

    ltr_image = Image.new("RGB", (1100, 180), (255, 255, 255))
    ltr_draw = ImageDraw.Draw(ltr_image)
    ltr_draw.text(
        (1030, 55),
        BIDI_NIQQUD_LINES[2],
        font=font,
        fill=(20, 18, 15),
        anchor="ra",
        direction="ltr",
    )
    direction_diff_pixels = sum(
        1 for pixel in _image_pixels(ImageChops.difference(rtl_image, ltr_image)) if pixel != (0, 0, 0)
    )
    assert direction_diff_pixels > 1_000


def test_font_shaping_audit_reports_missing_raqm_as_environment_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pillow_has_raqm.cache_clear()
    try:
        monkeypatch.setattr(
            generator_module.features,
            "check",
            lambda feature: False if feature == "raqm" else True,
        )

        assert not features.check("raqm")
        with pytest.raises(RuntimeError, match="requires Pillow with libraqm support for Hebrew RTL rendering"):
            _require_raqm()

        image = Image.new("RGB", (200, 100), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        with pytest.raises(RuntimeError, match="requires Pillow with libraqm support for Hebrew RTL rendering"):
            _draw_rtl_text(draw, (180, 40), HEBREW_CONTRACT_LINE, font=object(), fill=(0, 0, 0))
    finally:
        _pillow_has_raqm.cache_clear()


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


def test_archive_card_generation_preserves_v1_provenance_and_hebrew_text(tmp_path: Path) -> None:
    documents = generate_documents(
        count=1,
        seed=37,
        template_ids=["archive_card"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / "archive-card",
    )

    [document] = documents
    assert document.template_id == "archive_card"
    assert document.recipe_id == "archive_card_identifier_v1"
    assert document.degradation_preset == "office_scan_soft"
    assert document.font_id == "alef-regular"
    assert document.title == "כרטיס ארכיון"
    assert document.logical_text == unicodedata.normalize("NFC", document.logical_text)
    document_lines = document.logical_text.splitlines()
    assert document_lines[0] == "כרטיס ארכיון"
    assert document_lines[1].startswith("מזהה א-")
    assert any(line == "ארכיון" for line in document_lines)
    assert document.footer.startswith("עמוד ")
    assert " - א-" in document.footer
    assert document.footer == document_lines[-1]
    assert document.path.is_file()
    assert not PurePosixPath(document.asset_path).is_absolute()

    manifest = generate_batch(
        count=1,
        seed=37,
        output_dir=tmp_path / "archive-card-manifest",
        template_ids=["archive_card"],
    ).to_dict()
    [sample] = manifest["samples"]
    assert sample["recipe_id"] == "archive_card_identifier_v1"
    assert sample["provenance"] == {
        "seed": 37,
        "sample_index": 0,
        "template_id": "archive_card",
        "recipe_id": "archive_card_identifier_v1",
        "degradation_preset": "office_scan_soft",
        "font_id": "alef-regular",
        "source_corpus": "packaged:synthetic/texts/hebrew_lines.txt",
    }
    assert sample["text"]["direction"] == "rtl"
    assert sample["text"]["unicode_normalization"] == "NFC"
    logical_lines = sample["text"]["logical_order"].splitlines()
    assert logical_lines[0] == "כרטיס ארכיון"
    assert logical_lines[1].startswith("מזהה א-")
    assert any(line == "ארכיון" for line in logical_lines)
    assert logical_lines[-1].startswith("עמוד ")
    assert " - א-" in logical_lines[-1]


def test_archive_card_manifest_text_matches_rendered_body_overflow(tmp_path: Path) -> None:
    corpus_path = tmp_path / "long_archive_card_corpus.txt"
    corpus_path.write_text(
        " ".join(f"מילה{index:02d}" for index in range(80)) + "\n",
        encoding="utf-8",
    )

    documents = generate_documents(
        count=1,
        seed=37,
        template_ids=["archive_card"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=corpus_path,
        output_dir=tmp_path / "archive-card-overflow",
    )

    [document] = documents
    body_lines = document.body.splitlines()
    logical_lines = document.logical_text.splitlines()

    assert 1 <= len(body_lines) <= 7
    assert body_lines == logical_lines[3 : 3 + len(body_lines)]
    assert "מילה79" not in document.logical_text
    assert logical_lines[-6:] == ["מקור", "תאריך", "מספר", "הערה", "ארכיון", document.footer]


@pytest.mark.parametrize(
    ("base_template_id", "variant_template_id", "recipe_id", "degradation_preset", "font_id"),
    DEGRADATION_VARIANT_CASES,
)
def test_degradation_template_variants_are_deterministic_and_cataloged(
    tmp_path: Path,
    base_template_id: str,
    variant_template_id: str,
    recipe_id: str,
    degradation_preset: str,
    font_id: str,
) -> None:
    first_dir = tmp_path / f"{variant_template_id}-first"
    second_dir = tmp_path / f"{variant_template_id}-second"
    first = generate_batch(
        count=1,
        seed=43,
        output_dir=first_dir,
        template_ids=[variant_template_id],
    ).to_dict()
    second = generate_batch(
        count=1,
        seed=43,
        output_dir=second_dir,
        template_ids=[variant_template_id],
    ).to_dict()

    assert first == second
    [sample] = first["samples"]
    assert sample["recipe_id"] == recipe_id
    assert sample["provenance"] == {
        "seed": 43,
        "sample_index": 0,
        "template_id": variant_template_id,
        "recipe_id": recipe_id,
        "degradation_preset": degradation_preset,
        "font_id": font_id,
        "source_corpus": "packaged:synthetic/texts/hebrew_lines.txt",
    }
    catalog = {entry.template_id: entry for entry in template_catalog()}
    assert catalog[variant_template_id].recipe_id == recipe_id
    assert catalog[variant_template_id].degradation_preset == degradation_preset
    assert catalog[variant_template_id].font_id == font_id
    assert catalog[base_template_id].degradation_preset != degradation_preset
    assert _degradation_preset(degradation_preset).jpeg_quality < _degradation_preset(
        catalog[base_template_id].degradation_preset
    ).jpeg_quality


@pytest.mark.parametrize(
    ("base_template_id", "variant_template_id", "_recipe_id", "_degradation_preset", "_font_id"),
    DEGRADATION_VARIANT_CASES,
)
def test_stronger_degradation_variants_change_visual_smoke_metrics(
    tmp_path: Path,
    base_template_id: str,
    variant_template_id: str,
    _recipe_id: str,
    _degradation_preset: str,
    _font_id: str,
) -> None:
    base_documents = generate_documents(
        count=1,
        seed=47,
        template_ids=[base_template_id],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / base_template_id,
    )
    variant_documents = generate_documents(
        count=1,
        seed=47,
        template_ids=[variant_template_id],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / variant_template_id,
    )

    base_document = base_documents[0]
    variant_document = variant_documents[0]
    assert base_document.sha256 != variant_document.sha256
    assert base_document.logical_text == variant_document.logical_text

    with Image.open(base_document.path).convert("RGB") as base_image:
        with Image.open(variant_document.path).convert("RGB") as variant_image:
            assert _changed_pixel_count(base_image, variant_image) > 900_000
            assert _mean_luminance(base_image) - _mean_luminance(variant_image) > 8.0
            assert _mean_edge_strength(base_image) > _mean_edge_strength(variant_image)
            assert _dark_ink_pixel_count(variant_image) > 6_000

            if base_template_id == "printed_letter":
                form_region = variant_image.crop((140, 330, 1060, 820))
                assert _dark_ink_pixel_count(form_region) > 8_000
                assert _red_stamp_pixel_count(variant_image) > 700
                assert _ruled_pixel_count(form_region) > 100_000
            elif base_template_id == "handwritten_note":
                marginalia_region = variant_image.crop((120, 430, 280, 760))
                assert _dark_ink_pixel_count(marginalia_region) > 50
                assert _dark_ink_pixel_count(variant_image) > 20_000
            else:
                card_region = variant_image.crop((170, 230, 1030, 1260))
                assert _dark_ink_pixel_count(card_region) > 5_000
                assert _red_stamp_pixel_count(card_region) > 300
                assert _ruled_pixel_count(card_region) > 100_000


def test_archive_card_faded_scan_preserves_rendered_logical_text_boundary(tmp_path: Path) -> None:
    documents = generate_documents(
        count=1,
        seed=37,
        template_ids=["archive_card_faded_scan"],
        font_manifest_path=default_font_manifest_path(),
        text_corpus_path=default_text_corpus_path(),
        output_dir=tmp_path / "archive-card-faded",
    )

    [document] = documents
    assert document.template_id == "archive_card_faded_scan"
    assert document.recipe_id == "archive_card_identifier_faded_scan_v1"
    assert document.degradation_preset == "archive_scan_faded"
    logical_lines = document.logical_text.splitlines()
    assert logical_lines[0] == "כרטיס ארכיון"
    assert logical_lines[1].startswith("מזהה א-")
    assert "ארכיון" in logical_lines
    assert logical_lines[-1] == document.footer
    assert " - א-" in document.footer
    assert document.logical_text == unicodedata.normalize("NFC", document.logical_text)


def test_template_catalog_resolves_packaged_fonts_by_style() -> None:
    catalog = {entry.template_id: entry for entry in template_catalog()}

    assert catalog["printed_letter"].recipe_id == "printed_letter_form_v1"
    assert catalog["printed_letter"].degradation_preset == "office_scan_soft"
    assert catalog["printed_letter"].font_style == "printed"
    assert catalog["printed_letter"].font_id == "alef-regular"
    assert catalog["handwritten_note"].recipe_id == "handwritten_note_marginalia_v1"
    assert catalog["handwritten_note"].degradation_preset == "notebook_scan_worn"
    assert catalog["handwritten_note"].font_style == "handwritten_like"
    assert catalog["handwritten_note"].font_id == "gveret-levin-regular"
    assert catalog["archive_card"].recipe_id == "archive_card_identifier_v1"
    assert catalog["archive_card"].layout_style == "multi_region_page"
    assert catalog["archive_card"].degradation_preset == "office_scan_soft"
    assert catalog["archive_card"].font_style == "printed"
    assert catalog["archive_card"].font_id == "alef-regular"
    assert catalog["printed_letter_heavy_scan"].recipe_id == "printed_letter_form_heavy_scan_v1"
    assert catalog["printed_letter_heavy_scan"].degradation_preset == "office_scan_heavy"
    assert catalog["printed_letter_heavy_scan"].font_style == "printed"
    assert catalog["printed_letter_heavy_scan"].font_id == "alef-regular"
    assert catalog["handwritten_note_heavy_wear"].recipe_id == "handwritten_note_marginalia_heavy_wear_v1"
    assert catalog["handwritten_note_heavy_wear"].degradation_preset == "notebook_scan_heavy_wear"
    assert catalog["handwritten_note_heavy_wear"].font_style == "handwritten_like"
    assert catalog["handwritten_note_heavy_wear"].font_id == "gveret-levin-regular"
    assert catalog["archive_card_faded_scan"].recipe_id == "archive_card_identifier_faded_scan_v1"
    assert catalog["archive_card_faded_scan"].degradation_preset == "archive_scan_faded"
    assert catalog["archive_card_faded_scan"].font_style == "printed"
    assert catalog["archive_card_faded_scan"].font_id == "alef-regular"


def test_template_catalog_rejects_malformed_or_missing_style_font_manifest(tmp_path: Path) -> None:
    malformed_manifest_path = tmp_path / "malformed.yaml"
    malformed_manifest_path.write_text("not_fonts: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing a valid 'fonts' list"):
        template_catalog(font_manifest_path=malformed_manifest_path)

    missing_style_manifest_path = tmp_path / "missing-style.yaml"
    missing_style_manifest_path.write_text(
        "fonts:\n  - id: alef-regular\n    file: Alef-Regular.ttf\n    style: printed\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No synthetic font registered for style: handwritten_like"):
        template_catalog(["handwritten_note"], font_manifest_path=missing_style_manifest_path)

    missing_file_manifest_path = tmp_path / "missing-file.yaml"
    missing_file_manifest_path.write_text(
        "fonts:\n  - id: missing-font\n    file: missing.ttf\n    style: printed\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Synthetic font file is missing"):
        template_catalog(["printed_letter"], font_manifest_path=missing_file_manifest_path)

    invalid_font_manifest_path = tmp_path / "invalid-font.yaml"
    (tmp_path / "invalid.ttf").write_bytes(b"not a font")
    invalid_font_manifest_path.write_text(
        "fonts:\n  - id: invalid-font\n    file: invalid.ttf\n    style: printed\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Synthetic font file is invalid or unreadable"):
        template_catalog(["printed_letter"], font_manifest_path=invalid_font_manifest_path)


def test_synthetic_visual_recipes_render_expected_page_features(tmp_path: Path) -> None:
    documents = generate_documents(
        count=3,
        seed=31,
        template_ids=["printed_letter", "handwritten_note", "archive_card"],
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

    with Image.open(by_template["archive_card"].path).convert("RGB") as archive_card:
        card_region = archive_card.crop((170, 230, 1030, 1260))
        card_pixels = _image_pixels(card_region)
        red_stamp_pixels = sum(1 for r, g, b in card_pixels if r > 90 and r > g * 1.45 and r > b * 1.45)
        ruled_pixels = sum(1 for r, g, b in card_pixels if 145 <= r <= 225 and 135 <= g <= 215 and 115 <= b <= 200)
        dark_ink_pixels = sum(1 for r, g, b in card_pixels if r < 115 and g < 105 and b < 95)
        assert red_stamp_pixels > 350
        assert ruled_pixels > 10_000
        assert dark_ink_pixels > 4_000


def test_synthetic_generation_rejects_invalid_inputs(tmp_path: Path) -> None:
    invalid_template_output = tmp_path / "invalid-template"
    with pytest.raises(ValueError, match="Unsupported synthetic template_id: typo_template"):
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
        "fonts:\n  - id: missing-font\n    file: missing.ttf\n    style: printed\n",
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
        "fonts:\n  - id: invalid-font\n    file: invalid.ttf\n    style: printed\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Synthetic font file is invalid or unreadable"):
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
        generate_batch(count=1, seed=7, output_dir=tmp_path / "empty-templates", template_ids=[])
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
    assert _select_font(
        [{"id": "alef-regular", "style": "printed"}], "archive_card"
    ) == {
        "id": "alef-regular",
        "style": "printed",
    }
    assert _select_font(
        [{"id": "gveret-levin-regular", "style": "handwritten_like"}], "handwritten_note"
    ) == {
        "id": "gveret-levin-regular",
        "style": "handwritten_like",
    }
    with pytest.raises(ValueError, match="No synthetic font registered"):
        _select_font([{"id": "alef-regular", "style": "printed"}], "handwritten_note")

    image = Image.new("RGB", (600, 400), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _load_font(_font_path(default_font_manifest_path(), {"id": "alef-regular", "file": "Alef-Regular.ttf"}), 42)
    assert _wrap_hebrew_text(draw, "", font, max_width=200) == [""]
    assert len(_wrap_hebrew_text(draw, "מכתב מנהלי רישום ארכיוני הודעה פנימית", font, max_width=100)) > 1


def test_generation_requires_raqm_for_hebrew_rendering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _pillow_has_raqm.cache_clear()
    monkeypatch.setattr(generator_module.features, "check", lambda feature: False if feature == "raqm" else True)

    with pytest.raises(RuntimeError, match="requires Pillow with libraqm support"):
        generate_batch(count=1, seed=17, output_dir=tmp_path)

    _pillow_has_raqm.cache_clear()
