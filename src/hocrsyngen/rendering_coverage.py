from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any, TypeAlias

from PIL import Image, UnidentifiedImageError, features

from hocrsyngen.generator import (
    GENERATOR_VERSION,
    GOVERNED_TEMPLATE_IDS,
    template_catalog,
)
from hocrsyngen.manifest import GenerationManifest


RENDERING_COVERAGE_REPORT_FILENAME = "rendering_coverage_report.json"
RENDERING_COVERAGE_REPORT_VERSION = "rendering_coverage_report.v1"

EXPECTED_TEXT_FEATURES = (
    "final_forms",
    "punctuation",
    "numerals",
    "dates",
    "identifiers",
    "latin_fragments",
    "sparse_niqqud",
    "fuller_niqqud",
    "nfc_logical_order_text",
)
EXPECTED_BIDI_MIXED_DIRECTION = (
    "hebrew_latin_fragments",
    "hebrew_numeric_fragments",
    "hebrew_punctuation",
)
EXPECTED_RENDERING_PATH = (
    "logical_order_text",
    "rtl_text_metadata",
    "shared_rtl_draw_path",
)
EXPECTED_ASSET_SMOKE = (
    "readable_jpeg",
    "declared_dimensions_match",
    "non_empty_ink",
)
EvidenceValue: TypeAlias = str | bool | int | float | list[str]
EvidenceEntry: TypeAlias = dict[str, EvidenceValue]

_HEBREW_RE = re.compile(r"[\u0590-\u05ff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_NUMERAL_RE = re.compile(r"\d")
_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_IDENTIFIER_RE = re.compile(
    r"\b[A-Za-z]+-[A-Za-z0-9\u0590-\u05ff-]*\d[A-Za-z0-9\u0590-\u05ff-]*\b"
    r"|[\u0590-\u05ff]-\d{2,5}-\d{1,3}"
    r"|מספר תיק \d+/\d+"
    r"|מזהה [^\s]+"
)
_PUNCTUATION_RE = re.compile(r"""[.,:;!?'"()\-/"]""")


def build_rendering_coverage_report(
    manifest: GenerationManifest,
    batch_dir: Path,
) -> dict[str, Any]:
    payload = manifest.to_dict()
    samples = payload["samples"]
    page_count = sum(len(sample["pages"]) for sample in samples)
    catalog = template_catalog(GOVERNED_TEMPLATE_IDS)
    expected = {
        "fonts": sorted({entry.font_id for entry in catalog}),
        "templates": sorted({entry.template_id for entry in catalog}),
        "recipes": sorted({entry.recipe_id for entry in catalog}),
        "degradation_presets": sorted({entry.degradation_preset for entry in catalog}),
    }

    coverage = {
        "fonts": _coverage_entry(
            covered=sorted(
                {sample["provenance"]["font_id"] for sample in samples}
            ),
            expected=expected["fonts"],
            evidence=_sample_evidence_by_provenance(samples, "font_id"),
        ),
        "templates": _coverage_entry(
            covered=sorted(
                {sample["provenance"]["template_id"] for sample in samples}
            ),
            expected=expected["templates"],
            evidence=_sample_evidence_by_provenance(samples, "template_id"),
        ),
        "recipes": _coverage_entry(
            covered=sorted({sample["recipe_id"] for sample in samples}),
            expected=expected["recipes"],
            evidence=_sample_evidence_by_sample_key(samples, "recipe_id"),
        ),
        "degradation_presets": _coverage_entry(
            covered=sorted(
                {sample["provenance"]["degradation_preset"] for sample in samples}
            ),
            expected=expected["degradation_presets"],
            evidence=_sample_evidence_by_provenance(samples, "degradation_preset"),
        ),
        "text_features": _text_feature_coverage(samples),
        "bidi_mixed_direction": _bidi_mixed_direction_coverage(samples),
        "rendering_path": _rendering_path_coverage(samples),
        "asset_smoke": _asset_smoke_coverage(samples, batch_dir),
    }

    limitations = _limitations(coverage, page_count=page_count)
    return {
        "report_version": RENDERING_COVERAGE_REPORT_VERSION,
        "generator_name": "hocrsyngen",
        "generator_version": GENERATOR_VERSION,
        "batch": {
            "manifest_path": "generation_manifest.json",
            "sample_count": len(samples),
            "page_count": page_count,
        },
        "environment": {
            "pillow_raqm": _feature_available("raqm"),
            "shaping_stack": {
                "libraqm": _feature_status("raqm"),
                "fribidi": _feature_status("fribidi"),
                "harfbuzz": _feature_status("harfbuzz"),
            },
        },
        "coverage": coverage,
        "limitations": limitations,
    }


def write_rendering_coverage_report(
    manifest: GenerationManifest,
    batch_dir: Path,
) -> Path:
    report = build_rendering_coverage_report(manifest, batch_dir)
    path = batch_dir / RENDERING_COVERAGE_REPORT_FILENAME
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _coverage_entry(
    *,
    covered: list[str],
    expected: list[str] | tuple[str, ...],
    evidence: list[EvidenceEntry],
) -> dict[str, Any]:
    covered_set = set(covered)
    return {
        "covered": covered,
        "missing": [value for value in expected if value not in covered_set],
        "evidence": evidence,
    }


def _sample_evidence_by_provenance(
    samples: list[dict[str, Any]],
    provenance_key: str,
) -> list[EvidenceEntry]:
    evidence = []
    for sample in samples:
        for page in sample["pages"]:
            evidence.append(
                {
                    "sample_id": sample["sample_id"],
                    "asset_path": _portable_path(page["asset_path"]),
                    provenance_key: sample["provenance"][provenance_key],
                }
            )
    return evidence


def _sample_evidence_by_sample_key(
    samples: list[dict[str, Any]],
    sample_key: str,
) -> list[EvidenceEntry]:
    evidence = []
    for sample in samples:
        for page in sample["pages"]:
            evidence.append(
                {
                    "sample_id": sample["sample_id"],
                    "asset_path": _portable_path(page["asset_path"]),
                    sample_key: sample[sample_key],
                }
            )
    return evidence


def _text_feature_coverage(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_features = {
        sample["sample_id"]: _text_features_for_sample(sample)
        for sample in samples
    }
    covered = _ordered_union(sample_features.values(), EXPECTED_TEXT_FEATURES)
    return _coverage_entry(
        covered=covered,
        expected=EXPECTED_TEXT_FEATURES,
        evidence=_feature_evidence(samples, sample_features),
    )


def _bidi_mixed_direction_coverage(samples: list[dict[str, Any]]) -> dict[str, Any]:
    sample_features = {
        sample["sample_id"]: _bidi_features_for_sample(sample)
        for sample in samples
    }
    covered = _ordered_union(sample_features.values(), EXPECTED_BIDI_MIXED_DIRECTION)
    return _coverage_entry(
        covered=covered,
        expected=EXPECTED_BIDI_MIXED_DIRECTION,
        evidence=_feature_evidence(samples, sample_features),
    )


def _rendering_path_coverage(samples: list[dict[str, Any]]) -> dict[str, Any]:
    covered = []
    if samples and all(sample["text"]["logical_order"] for sample in samples):
        covered.append("logical_order_text")
    if samples and all(
        sample["text"]["direction"] == "rtl"
        and sample["text"]["script"] == "Hebr"
        and sample["text"]["unicode_normalization"] == "NFC"
        for sample in samples
    ):
        covered.append("rtl_text_metadata")
    if samples and _feature_available("raqm"):
        covered.append("shared_rtl_draw_path")
    return _coverage_entry(
        covered=covered,
        expected=EXPECTED_RENDERING_PATH,
        evidence=_batch_text_evidence(samples, covered),
    )


def _asset_smoke_coverage(
    samples: list[dict[str, Any]],
    batch_dir: Path,
) -> dict[str, Any]:
    evidence = []
    for sample in samples:
        for page in sample["pages"]:
            asset_path = _portable_path(page["asset_path"])
            smoke = _asset_smoke(
                batch_dir / Path(*PurePosixPath(asset_path).parts), page
            )
            evidence.append(
                {
                    "sample_id": sample["sample_id"],
                    "asset_path": asset_path,
                    "readable_jpeg": smoke["readable_jpeg"],
                    "declared_dimensions_match": smoke["declared_dimensions_match"],
                    "non_empty_ink": smoke["non_empty_ink"],
                }
            )
    covered = [
        value
        for value in EXPECTED_ASSET_SMOKE
        if evidence and all(bool(entry[value]) for entry in evidence)
    ]
    return _coverage_entry(
        covered=covered,
        expected=EXPECTED_ASSET_SMOKE,
        evidence=evidence,
    )


def _asset_smoke(path: Path, page: dict[str, Any]) -> dict[str, bool]:
    smoke = {
        "readable_jpeg": False,
        "declared_dimensions_match": False,
        "non_empty_ink": False,
    }
    try:
        with Image.open(path) as image:
            image.load()
            smoke["readable_jpeg"] = image.format == "JPEG"
            smoke["declared_dimensions_match"] = image.size == (
                page["width"],
                page["height"],
            )
            rgb = image.convert("RGB")
            pixels = rgb.tobytes()
            smoke["non_empty_ink"] = any(
                pixels[index] < 180
                and pixels[index + 1] < 180
                and pixels[index + 2] < 180
                for index in range(0, len(pixels), 3)
            )
    except (OSError, UnidentifiedImageError):
        pass
    return smoke


def _text_features_for_sample(sample: dict[str, Any]) -> list[str]:
    text = sample["text"]["logical_order"]
    covered = []
    if any(character in text for character in "ךםןףץ"):
        covered.append("final_forms")
    if _PUNCTUATION_RE.search(text):
        covered.append("punctuation")
    if _NUMERAL_RE.search(text):
        covered.append("numerals")
    if _DATE_RE.search(text):
        covered.append("dates")
    if _IDENTIFIER_RE.search(text):
        covered.append("identifiers")
    if _LATIN_RE.search(text):
        covered.append("latin_fragments")
    if _hebrew_mark_count(text):
        covered.append("sparse_niqqud")
    if _has_fuller_niqqud_token(text):
        covered.append("fuller_niqqud")
    if text == unicodedata.normalize("NFC", text):
        covered.append("nfc_logical_order_text")
    return covered


def _bidi_features_for_sample(sample: dict[str, Any]) -> list[str]:
    text = sample["text"]["logical_order"]
    has_hebrew = bool(_HEBREW_RE.search(text))
    covered = []
    if has_hebrew and _LATIN_RE.search(text):
        covered.append("hebrew_latin_fragments")
    if has_hebrew and _NUMERAL_RE.search(text):
        covered.append("hebrew_numeric_fragments")
    if has_hebrew and _PUNCTUATION_RE.search(text):
        covered.append("hebrew_punctuation")
    return covered


def _feature_evidence(
    samples: list[dict[str, Any]],
    sample_features: dict[str, list[str]],
) -> list[EvidenceEntry]:
    evidence = []
    for sample in samples:
        covered = sample_features[sample["sample_id"]]
        if not covered:
            continue
        entry: EvidenceEntry = {
            "sample_id": sample["sample_id"],
            "covered": covered,
        }
        if sample["pages"]:
            entry["asset_path"] = _portable_path(sample["pages"][0]["asset_path"])
        evidence.append(entry)
    return evidence


def _batch_text_evidence(
    samples: list[dict[str, Any]],
    dimensions: list[str],
) -> list[EvidenceEntry]:
    if not dimensions:
        return []
    evidence = []
    for sample in samples:
        entry: EvidenceEntry = {
            "sample_id": sample["sample_id"],
            "covered": dimensions,
        }
        if sample["pages"]:
            entry["asset_path"] = _portable_path(sample["pages"][0]["asset_path"])
        evidence.append(entry)
    return evidence


def _ordered_union(
    values: Iterable[list[str]],
    expected_order: tuple[str, ...],
) -> list[str]:
    covered = set()
    for feature_list in values:
        covered.update(feature_list)
    return [feature for feature in expected_order if feature in covered]


def _limitations(coverage: dict[str, Any], *, page_count: int) -> list[str]:
    limitations = []
    for dimension, entry in coverage.items():
        if entry["missing"]:
            limitations.append(
                f"{dimension} missing coverage: {', '.join(entry['missing'])}"
            )
    if page_count == 0:
        limitations.append(
            "No page assets were available for rendering smoke evidence."
        )
    return limitations


def _portable_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(
            f"Rendering coverage paths must be relative portable paths: {value}"
        )
    return value


def _is_hebrew_mark(character: str) -> bool:
    return "\u0591" <= character <= "\u05c7" and unicodedata.combining(character) != 0


def _hebrew_mark_count(text: str) -> int:
    return sum(1 for character in text if _is_hebrew_mark(character))


def _has_fuller_niqqud_token(text: str) -> bool:
    return any(_hebrew_mark_count(token) >= 4 for token in text.split())


def _feature_available(feature: str) -> bool:
    try:
        return bool(features.check(feature))
    except ValueError:
        return False


def _feature_status(feature: str) -> str:
    if _feature_available(feature):
        try:
            version = features.version(feature)
        except ValueError:
            version = None
        return str(version) if version else "available"
    return "missing"
