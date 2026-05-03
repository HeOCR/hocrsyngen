from __future__ import annotations

import copy
import json
import re
import shutil
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import pytest

from hocrsyngen.cli import main
from hocrsyngen.generator import template_catalog
from hocrsyngen.validation import BatchValidationError, validate_batch


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "generation_manifest_v1.md"
SCHEMA_PATH = (
    REPO_ROOT
    / "src"
    / "hocrsyngen"
    / "schemas"
    / "generation_manifest.schema.json"
)
EXPECTED_MANIFEST_VERSION = "1.0"
EXPECTED_GENERATOR_NAME = "hocrsyngen"
EXPECTED_PROJECT_SYNTHETIC_LICENSE = "PROJECT-SYNTHETIC"
EXPECTED_SYNTHETIC_DISCLOSURE = (
    "Generated synthetic Hebrew OCR/HTR sample. It is candidate synthetic input for "
    "hocrgen governance and is not real-source provenance."
)

EXPECTED_TOP_LEVEL_FIELDS = {
    "manifest_version",
    "generator_name",
    "license",
    "synthetic_disclosure",
    "samples",
}
EXPECTED_SAMPLE_FIELDS = {
    "sample_id",
    "pages",
    "text",
    "generator_version",
    "recipe_id",
    "provenance",
    "license",
    "synthetic_disclosure",
    "controls",
}
EXPECTED_PAGE_FIELDS = {
    "page_id",
    "asset_path",
    "media_type",
    "sha256",
    "width",
    "height",
}
EXPECTED_TEXT_FIELDS = {
    "logical_order",
    "script",
    "language",
    "direction",
    "unicode_normalization",
}
EXPECTED_PROVENANCE_FIELDS = {
    "seed",
    "sample_index",
    "template_id",
    "recipe_id",
    "degradation_preset",
    "font_id",
    "source_corpus",
}
EXPECTED_CONTROL_FIELDS = {"persona", "condition"}
EXPECTED_SCHEMA_NODES = [
    (),
    ("$defs", "sample"),
    ("$defs", "pageAsset"),
    ("$defs", "textMetadata"),
    ("$defs", "provenance"),
    ("$defs", "controls"),
]
FIXTURE_REGENERATION_SEED = 17
FIXTURE_REGENERATION_COUNT = 2
RENDER_STACK_DEPENDENT_SHA256 = "<render-stack-dependent>"
EXPECTED_PACKAGED_FIXTURE_PAGE_SHA256 = {
    "assets/hocrsyngen-s00000017-000000/page_0001.jpg": (
        "50700a08f555ae3273e4c7c2f19544a8ff4b307af4cbc52eb9d986c43f6c09fd"
    ),
    "assets/hocrsyngen-s00000017-000001/page_0001.jpg": (
        "4615d215ec2e8ea5b13750f09f6da41a07075d1f74554812cc25cd4f5238b428"
    ),
}


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_contract_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _documented_fields(section_title: str) -> set[str]:
    doc = _load_contract_doc()
    match = re.search(
        rf"^## {re.escape(section_title)}\n(?P<body>.*?)(?=^## |\Z)",
        doc,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Missing documentation section: {section_title}"
    return set(re.findall(r"^- `([^`]+)`:", match.group("body"), flags=re.MULTILINE))


def _schema_node(schema: dict[str, Any], *path: str) -> dict[str, Any]:
    node: dict[str, Any] = schema
    for part in path:
        node = node[part]
    return node


def _packaged_contract_fixture() -> Path:
    return (
        resources.files("hocrsyngen")
        / "data"
        / "contracts"
        / "generation_manifest_v1"
        / "fixture-batch"
    )


def _load_packaged_fixture_manifest(batch_dir: Path) -> dict[str, Any]:
    return json.loads(
        (batch_dir / "generation_manifest.json").read_text(encoding="utf-8")
    )


def _fixture_payload() -> dict[str, Any]:
    with resources.as_file(_packaged_contract_fixture()) as batch_dir:
        return _load_packaged_fixture_manifest(batch_dir)


def _stable_manifest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    stable = copy.deepcopy(payload)
    for sample in stable["samples"]:
        for page in sample["pages"]:
            page["sha256"] = RENDER_STACK_DEPENDENT_SHA256
    return stable


def _copy_packaged_contract_fixture(target: Path) -> Path:
    with resources.as_file(_packaged_contract_fixture()) as batch_dir:
        shutil.copytree(batch_dir, target)
    return target


def _with_field_deleted(payload: dict[str, Any], path: tuple[Any, ...]) -> dict[str, Any]:
    changed = copy.deepcopy(payload)
    target: Any = changed
    for part in path[:-1]:
        target = target[part]
    del target[path[-1]]
    return changed


def _with_extra_field(payload: dict[str, Any], path: tuple[Any, ...]) -> dict[str, Any]:
    changed = copy.deepcopy(payload)
    target: Any = changed
    for part in path:
        target = target[part]
    target["unexpected_contract_field"] = True
    return changed


def test_manifest_contract_doc_fields_match_schema_required_fields() -> None:
    schema = _load_schema()

    assert set(schema["required"]) == EXPECTED_TOP_LEVEL_FIELDS
    assert set(schema["properties"]) == EXPECTED_TOP_LEVEL_FIELDS
    assert _documented_fields("Top-Level Fields") == EXPECTED_TOP_LEVEL_FIELDS

    sample_schema = schema["$defs"]["sample"]
    assert set(sample_schema["required"]) == EXPECTED_SAMPLE_FIELDS
    assert set(sample_schema["properties"]) == EXPECTED_SAMPLE_FIELDS
    assert _documented_fields("Sample Fields") == EXPECTED_SAMPLE_FIELDS

    page_schema = schema["$defs"]["pageAsset"]
    assert set(page_schema["required"]) == EXPECTED_PAGE_FIELDS
    assert set(page_schema["properties"]) == EXPECTED_PAGE_FIELDS
    assert _documented_fields("Page Fields") == EXPECTED_PAGE_FIELDS

    text_schema = schema["$defs"]["textMetadata"]
    assert set(text_schema["required"]) == EXPECTED_TEXT_FIELDS
    assert set(text_schema["properties"]) == EXPECTED_TEXT_FIELDS
    assert _documented_fields("Text Metadata") == EXPECTED_TEXT_FIELDS

    provenance_schema = schema["$defs"]["provenance"]
    assert set(provenance_schema["required"]) == EXPECTED_PROVENANCE_FIELDS
    assert set(provenance_schema["properties"]) == EXPECTED_PROVENANCE_FIELDS
    assert _documented_fields("Provenance Fields") == EXPECTED_PROVENANCE_FIELDS

    controls_schema = schema["$defs"]["controls"]
    assert set(controls_schema["required"]) == EXPECTED_CONTROL_FIELDS
    assert set(controls_schema["properties"]) == EXPECTED_CONTROL_FIELDS
    assert _documented_fields("Controls") == EXPECTED_CONTROL_FIELDS


def test_manifest_contract_schema_rejects_unknown_fields_at_every_object_level() -> None:
    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)

    for path in EXPECTED_SCHEMA_NODES:
        node = _schema_node(schema, *path)
        assert node["additionalProperties"] is False

    payload = _fixture_payload()
    validator = jsonschema.Draft202012Validator(schema)
    for path in [
        (),
        ("samples", 0),
        ("samples", 0, "pages", 0),
        ("samples", 0, "text"),
        ("samples", 0, "provenance"),
        ("samples", 0, "controls"),
    ]:
        errors = list(validator.iter_errors(_with_extra_field(payload, path)))

        assert len(errors) == 1
        assert errors[0].validator == "additionalProperties"


@pytest.mark.parametrize(
    ("path", "location"),
    [
        (("manifest_version",), "$"),
        (("samples", 0, "sample_id"), "$.samples[0]"),
        (("samples", 0, "pages", 0, "asset_path"), "$.samples[0].pages[0]"),
        (("samples", 0, "text", "language"), "$.samples[0].text"),
        (("samples", 0, "provenance", "font_id"), "$.samples[0].provenance"),
        (("samples", 0, "controls", "persona"), "$.samples[0].controls"),
    ],
)
def test_manifest_contract_validation_reports_required_field_drift(
    path: tuple[Any, ...], location: str, tmp_path: Path
) -> None:
    target = _copy_packaged_contract_fixture(tmp_path / "fixture-batch")

    manifest_path = target / "generation_manifest.json"
    payload = _with_field_deleted(
        json.loads(manifest_path.read_text(encoding="utf-8")), path
    )
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        BatchValidationError,
        match=rf"Manifest schema validation failed at {re.escape(location)}",
    ):
        validate_batch(target)


def test_manifest_contract_documented_constants_match_schema_and_validation() -> None:
    doc = _load_contract_doc()
    schema = _load_schema()

    assert f'must be `"{EXPECTED_MANIFEST_VERSION}"`' in doc
    assert f'must be `"{EXPECTED_PROJECT_SYNTHETIC_LICENSE}"`' in doc
    assert EXPECTED_SYNTHETIC_DISCLOSURE in doc
    assert f"`generator_name`: must be `\"{EXPECTED_GENERATOR_NAME}\"`." in doc
    assert "`media_type`: must be `image/jpeg`." in doc
    assert "`script`: must be `Hebr`." in doc
    assert "`language`: must be `he`." in doc
    assert "`direction`: must be `rtl`." in doc
    assert "`unicode_normalization`: must be `NFC`." in doc

    assert schema["properties"]["manifest_version"]["const"] == EXPECTED_MANIFEST_VERSION
    assert schema["properties"]["generator_name"]["const"] == EXPECTED_GENERATOR_NAME
    assert schema["properties"]["license"]["const"] == EXPECTED_PROJECT_SYNTHETIC_LICENSE
    assert (
        schema["properties"]["synthetic_disclosure"]["const"]
        == EXPECTED_SYNTHETIC_DISCLOSURE
    )
    assert (
        schema["$defs"]["sample"]["properties"]["license"]["const"]
        == EXPECTED_PROJECT_SYNTHETIC_LICENSE
    )
    assert (
        schema["$defs"]["sample"]["properties"]["synthetic_disclosure"]["const"]
        == EXPECTED_SYNTHETIC_DISCLOSURE
    )
    assert schema["$defs"]["pageAsset"]["properties"]["media_type"]["const"] == "image/jpeg"
    assert schema["$defs"]["textMetadata"]["properties"]["script"]["const"] == "Hebr"
    assert schema["$defs"]["textMetadata"]["properties"]["language"]["const"] == "he"
    assert schema["$defs"]["textMetadata"]["properties"]["direction"]["const"] == "rtl"
    assert schema["$defs"]["textMetadata"]["properties"]["unicode_normalization"]["const"] == "NFC"

    payload = _fixture_payload()
    assert payload["synthetic_disclosure"] == EXPECTED_SYNTHETIC_DISCLOSURE
    assert all(
        sample["synthetic_disclosure"] == EXPECTED_SYNTHETIC_DISCLOSURE
        for sample in payload["samples"]
    )


@pytest.mark.parametrize(
    ("path", "location"),
    [
        (("synthetic_disclosure",), "$"),
        (("samples", 0, "synthetic_disclosure"), "$.samples[0]"),
    ],
)
def test_manifest_contract_schema_rejects_synthetic_disclosure_drift(
    path: tuple[Any, ...], location: str, tmp_path: Path
) -> None:
    schema = _load_schema()
    payload = _fixture_payload()
    target: Any = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = "Generated synthetic sample with stale disclosure text."

    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(payload))
    assert len(errors) == 1
    assert errors[0].validator == "const"

    batch_dir = _copy_packaged_contract_fixture(tmp_path / "fixture-batch")
    manifest_path = batch_dir / "generation_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        BatchValidationError,
        match=rf"Manifest schema validation failed at {re.escape(location)}",
    ):
        validate_batch(batch_dir)


def test_manifest_contract_documented_governed_templates_match_catalog() -> None:
    doc = _load_contract_doc()

    for entry in template_catalog(["printed_letter", "handwritten_note"]):
        expected_row = (
            f"| `{entry.template_id}` | `{entry.recipe_id}` | "
            f"`{entry.degradation_preset}` | `{entry.font_id}` |"
        )
        assert expected_row in doc


def test_packaged_generation_manifest_fixture_matches_v1_contract_expectations() -> None:
    schema = _load_schema()

    with resources.as_file(_packaged_contract_fixture()) as batch_dir:
        payload = _load_packaged_fixture_manifest(batch_dir)
        result = validate_batch(batch_dir)

        jsonschema.validate(payload, schema)
        assert result.sample_count == 2
        assert result.page_count == 2

        assert set(payload) == EXPECTED_TOP_LEVEL_FIELDS
        assert payload == {
            "generator_name": EXPECTED_GENERATOR_NAME,
            "license": EXPECTED_PROJECT_SYNTHETIC_LICENSE,
            "manifest_version": EXPECTED_MANIFEST_VERSION,
            "samples": payload["samples"],
            "synthetic_disclosure": EXPECTED_SYNTHETIC_DISCLOSURE,
        }
        assert "schema_version" not in payload
        assert "generation_report" not in payload

        assert [sample["sample_id"] for sample in payload["samples"]] == [
            "hocrsyngen-s00000017-000000",
            "hocrsyngen-s00000017-000001",
        ]
        assert {
            sample["provenance"]["template_id"]: (
                sample["recipe_id"],
                sample["provenance"]["recipe_id"],
                sample["provenance"]["degradation_preset"],
                sample["provenance"]["font_id"],
            )
            for sample in payload["samples"]
        } == {
            "printed_letter": (
                "printed_letter_form_v1",
                "printed_letter_form_v1",
                "office_scan_soft",
                "alef-regular",
            ),
            "handwritten_note": (
                "handwritten_note_marginalia_v1",
                "handwritten_note_marginalia_v1",
                "notebook_scan_worn",
                "gveret-levin-regular",
            ),
        }

        for sample in payload["samples"]:
            assert set(sample) == EXPECTED_SAMPLE_FIELDS
            assert set(sample["text"]) == EXPECTED_TEXT_FIELDS
            assert sample["text"]["script"] == "Hebr"
            assert sample["text"]["language"] == "he"
            assert sample["text"]["direction"] == "rtl"
            assert sample["text"]["unicode_normalization"] == "NFC"
            assert set(sample["provenance"]) == EXPECTED_PROVENANCE_FIELDS
            assert sample["controls"] == {"persona": None, "condition": None}
            assert "schema_version" not in sample
            assert "generation_report" not in sample

            for page in sample["pages"]:
                assert set(page) == EXPECTED_PAGE_FIELDS
                asset_path = PurePosixPath(page["asset_path"])
                assert not asset_path.is_absolute()
                assert ".." not in asset_path.parts
                assert "\\" not in page["asset_path"]
                assert (batch_dir / Path(*asset_path.parts)).is_file()


def test_packaged_generation_manifest_fixture_is_reproducible_from_stable_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    regenerated_dir = tmp_path / "fixture-batch"

    assert (
        main(
            [
                "generate",
                "--count",
                str(FIXTURE_REGENERATION_COUNT),
                "--seed",
                str(FIXTURE_REGENERATION_SEED),
                "--output",
                str(regenerated_dir),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == ""
    regenerated_manifest = _load_packaged_fixture_manifest(regenerated_dir)

    with resources.as_file(_packaged_contract_fixture()) as packaged_dir:
        packaged_manifest = _load_packaged_fixture_manifest(packaged_dir)
        packaged_result = validate_batch(packaged_dir)
    regenerated_result = validate_batch(regenerated_dir)

    assert packaged_result.sample_count == FIXTURE_REGENERATION_COUNT
    assert packaged_result.page_count == FIXTURE_REGENERATION_COUNT
    assert regenerated_result.sample_count == packaged_result.sample_count
    assert regenerated_result.page_count == packaged_result.page_count
    assert {
        page["asset_path"]: page["sha256"]
        for sample in packaged_manifest["samples"]
        for page in sample["pages"]
    } == EXPECTED_PACKAGED_FIXTURE_PAGE_SHA256
    assert _stable_manifest_payload(regenerated_manifest) == _stable_manifest_payload(
        packaged_manifest
    )
    assert [
        (sample["sample_id"], sample["provenance"]["template_id"])
        for sample in packaged_manifest["samples"]
    ] == [
        ("hocrsyngen-s00000017-000000", "printed_letter"),
        ("hocrsyngen-s00000017-000001", "handwritten_note"),
    ]
    assert [
        (sample["provenance"]["seed"], sample["provenance"]["sample_index"])
        for sample in packaged_manifest["samples"]
    ] == [
        (FIXTURE_REGENERATION_SEED, 0),
        (FIXTURE_REGENERATION_SEED, 1),
    ]


@pytest.mark.parametrize(
    "asset_path",
    [
        "assets/hocrsyngen-s00000017-000000/page_0001.jpg",
        "/assets/page_0001.jpg",
        "../assets/page_0001.jpg",
        "assets\\page_0001.jpg",
        "C:/assets/page_0001.jpg",
    ],
)
def test_relative_posix_asset_path_contract_matches_documented_schema_pattern(
    asset_path: str,
) -> None:
    doc = _load_contract_doc()
    schema = _load_schema()
    payload = _fixture_payload()
    payload["samples"][0]["pages"][0]["asset_path"] = asset_path

    documented_pattern = json.dumps(schema["$defs"]["relativePath"]["pattern"])[1:-1]
    assert documented_pattern in doc

    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(payload))
    if asset_path == "assets/hocrsyngen-s00000017-000000/page_0001.jpg":
        assert errors == []
    else:
        assert len(errors) == 1
        assert errors[0].json_path == "$.samples[0].pages[0].asset_path"
