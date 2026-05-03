from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from importlib import resources
from json import JSONDecodeError
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
from PIL import Image, UnidentifiedImageError

from hocrsyngen.generator import GENERATOR_VERSION
from hocrsyngen.io import sha256_file
from hocrsyngen.manifest import (
    GENERATION_MANIFEST_VERSION,
    PROJECT_SYNTHETIC_LICENSE,
    SYNTHETIC_DISCLOSURE,
    PageAsset,
    TextMetadata,
)


MANIFEST_FILENAME = "generation_manifest.json"


@dataclass(frozen=True)
class ValidationResult:
    sample_count: int
    page_count: int


class BatchValidationError(ValueError):
    pass


def validate_batch(batch_dir: Path) -> ValidationResult:
    root = batch_dir.resolve()
    manifest_path = root / MANIFEST_FILENAME
    if not batch_dir.exists():
        raise BatchValidationError(f"Batch path does not exist: {batch_dir}")
    if not batch_dir.is_dir():
        raise BatchValidationError(f"Batch path is not a directory: {batch_dir}")
    if not manifest_path.is_file():
        raise BatchValidationError(f"Missing manifest: {manifest_path}")

    payload = _load_manifest_payload(manifest_path)
    _validate_manifest_schema(payload)
    _validate_manifest_constants(payload)

    page_count = 0
    for sample_index, sample in enumerate(payload["samples"]):
        _validate_text(sample["text"], sample_index)
        _validate_sample_constants(sample, sample_index)
        for page_index, page in enumerate(sample["pages"]):
            _validate_page(root, page, sample_index, page_index)
            page_count += 1
    return ValidationResult(sample_count=len(payload["samples"]), page_count=page_count)


def _load_manifest_payload(manifest_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise BatchValidationError(
            f"Malformed manifest JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise BatchValidationError(f"Could not read manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise BatchValidationError("Manifest must be a JSON object.")
    return payload


def _validate_manifest_schema(payload: dict[str, Any]) -> None:
    schema = json.loads(
        (
            resources.files("hocrsyngen")
            / "schemas"
            / "generation_manifest.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = _json_location(error.path)
        raise BatchValidationError(
            f"Manifest schema validation failed at {location}: {error.message}"
        )


def _validate_manifest_constants(payload: dict[str, Any]) -> None:
    if payload["manifest_version"] != GENERATION_MANIFEST_VERSION:
        raise BatchValidationError(
            "Manifest version does not match hocrsyngen manifest v1."
        )
    if payload["generator_name"] != "hocrsyngen":
        raise BatchValidationError("Manifest generator_name must be hocrsyngen.")
    if payload["license"] != PROJECT_SYNTHETIC_LICENSE:
        raise BatchValidationError("Manifest license must be PROJECT-SYNTHETIC.")
    if payload["synthetic_disclosure"] != SYNTHETIC_DISCLOSURE:
        raise BatchValidationError(
            "Manifest synthetic_disclosure does not match the hocrsyngen v1 disclosure."
        )


def _validate_sample_constants(sample: dict[str, Any], sample_index: int) -> None:
    location = f"samples[{sample_index}]"
    if sample["license"] != PROJECT_SYNTHETIC_LICENSE:
        raise BatchValidationError(f"{location}.license must be PROJECT-SYNTHETIC.")
    if sample["synthetic_disclosure"] != SYNTHETIC_DISCLOSURE:
        raise BatchValidationError(
            f"{location}.synthetic_disclosure does not match the hocrsyngen v1 disclosure."
        )
    if sample["generator_version"] != GENERATOR_VERSION:
        raise BatchValidationError(
            f"{location}.generator_version must be {GENERATOR_VERSION}."
        )
    if sample["recipe_id"] != sample["provenance"]["recipe_id"]:
        raise BatchValidationError(
            f"{location}.recipe_id must match provenance.recipe_id."
        )


def _validate_text(text: dict[str, Any], sample_index: int) -> None:
    location = f"samples[{sample_index}].text"
    try:
        TextMetadata(**text)
    except (TypeError, ValueError) as exc:
        raise BatchValidationError(f"{location}: {exc}") from exc
    logical_order = text["logical_order"]
    if logical_order != unicodedata.normalize("NFC", logical_order):
        raise BatchValidationError(f"{location}.logical_order must be NFC-normalized.")
    if text != {
        "logical_order": logical_order,
        "script": "Hebr",
        "language": "he",
        "direction": "rtl",
        "unicode_normalization": "NFC",
    }:
        raise BatchValidationError(f"{location} must retain Hebrew RTL metadata.")


def _validate_page(
    root: Path, page: dict[str, Any], sample_index: int, page_index: int
) -> None:
    location = f"samples[{sample_index}].pages[{page_index}]"
    try:
        PageAsset(**page)
    except (TypeError, ValueError) as exc:
        raise BatchValidationError(f"{location}: {exc}") from exc

    asset_path = _portable_asset_path(page["asset_path"], location)
    path = root / Path(*asset_path.parts)
    if not path.is_file():
        raise BatchValidationError(
            f"{location}.asset_path is missing: {page['asset_path']}"
        )
    if not path.resolve().is_relative_to(root):
        raise BatchValidationError(
            f"{location}.asset_path must stay under the batch directory: {page['asset_path']}"
        )

    actual_sha256 = sha256_file(path)
    if actual_sha256 != page["sha256"]:
        raise BatchValidationError(
            f"{location}.sha256 mismatch for {page['asset_path']}: expected {page['sha256']}, got {actual_sha256}"
        )

    _verify_image(path, location, page["asset_path"])
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "JPEG":
                raise BatchValidationError(
                    f"{location}.media_type mismatch for {page['asset_path']}: expected image/jpeg, got {image.format}"
                )
            if image.size != (page["width"], page["height"]):
                raise BatchValidationError(
                    f"{location} dimensions mismatch for {page['asset_path']}: "
                    f"expected {page['width']}x{page['height']}, got {image.size[0]}x{image.size[1]}"
                )
    except UnidentifiedImageError as exc:
        raise BatchValidationError(
            f"{location}.asset_path is not a readable image: {page['asset_path']}"
        ) from exc
    except OSError as exc:
        raise BatchValidationError(
            f"{location}.asset_path is not a valid image: {page['asset_path']}"
        ) from exc


def _verify_image(path: Path, location: str, asset_path: str) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except UnidentifiedImageError as exc:
        raise BatchValidationError(
            f"{location}.asset_path is not a readable image: {asset_path}"
        ) from exc
    except OSError as exc:
        raise BatchValidationError(
            f"{location}.asset_path is not a valid image: {asset_path}"
        ) from exc


def _portable_asset_path(value: str, location: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise BatchValidationError(
            f"{location}.asset_path must be a relative portable path: {value}"
        )
    return path


def _json_location(path: Any) -> str:
    parts = list(path)
    if not parts:
        return "$"
    location = "$"
    for part in parts:
        if isinstance(part, int):
            location += f"[{part}]"
        else:
            location += f".{part}"
    return location
