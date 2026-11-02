from __future__ import annotations

import json
import unicodedata
from collections.abc import Sequence
from importlib import resources
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import jsonschema

from hocrsyngen.generator import SyntheticDocument
from hocrsyngen.io import sha256_file
from hocrsyngen.manifest import GenerationManifest


LINE_ANNOTATIONS_FILENAME = "line_annotations.json"
LINE_ANNOTATIONS_SCHEMA_VERSION = "hocrsyngen_line_annotations.v1"
LINE_ANNOTATIONS_COORDINATE_SPACE = "final_page_pixels"
# A line continuing a logical_order line names how it joins the previous
# segment: wrapped body text joins with a space, ledger cells with " | ".
LOGICAL_JOIN_SEPARATORS = {"space": " ", "cell": " | "}


class LineAnnotationsError(ValueError):
    pass


def build_line_annotations(
    manifest: GenerationManifest,
    documents: Sequence[SyntheticDocument],
    manifest_path: Path,
) -> dict[str, Any]:
    documents_by_sample = {document.sample_id: document for document in documents}
    pages: list[dict[str, Any]] = []
    for sample in manifest.samples:
        document = documents_by_sample[sample.sample_id]
        if document.lines is None:
            raise LineAnnotationsError(
                f"Sample {sample.sample_id} was generated without line geometry recording."
            )
        for page in sample.pages:
            pages.append(
                {
                    "sample_id": sample.sample_id,
                    "page_id": page.page_id,
                    "page_sha256": page.sha256,
                    "width": page.width,
                    "height": page.height,
                    "lines": [
                        {
                            "line_index": line_index,
                            "logical_line_index": line.logical_line_index,
                            "logical_join": line.logical_join,
                            "occluded": line.occluded,
                            "region": line.region,
                            "text": line.text,
                            "polygon": [list(point) for point in line.polygon],
                            "baseline": [list(point) for point in line.baseline],
                        }
                        for line_index, line in enumerate(document.lines)
                    ],
                }
            )
    return {
        "schema": LINE_ANNOTATIONS_SCHEMA_VERSION,
        "generation_manifest_sha256": sha256_file(manifest_path),
        "coordinate_space": LINE_ANNOTATIONS_COORDINATE_SPACE,
        "pages": pages,
    }


def write_line_annotations(
    manifest: GenerationManifest,
    documents: Sequence[SyntheticDocument],
    manifest_path: Path,
) -> Path:
    payload = build_line_annotations(manifest, documents, manifest_path)
    path = manifest_path.parent / LINE_ANNOTATIONS_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def reconstruct_logical_lines(lines: Sequence[dict[str, Any]]) -> dict[int, str]:
    """Rebuild logical_order lines from one page's annotation lines.

    Lines with ``logical_line_index: null`` are drawn but not in
    ``logical_order`` and are skipped. Each logical line starts at a segment
    with ``logical_join: null``; later segments append with their separator.
    """

    rebuilt: dict[int, str] = {}
    for line in sorted(lines, key=lambda item: item["line_index"]):
        logical_line_index = line["logical_line_index"]
        if logical_line_index is None:
            continue
        join = line["logical_join"]
        if join is None:
            if logical_line_index in rebuilt:
                raise LineAnnotationsError(
                    f"Logical line {logical_line_index} has more than one segment with logical_join null."
                )
            rebuilt[logical_line_index] = line["text"]
        else:
            if logical_line_index not in rebuilt:
                raise LineAnnotationsError(
                    f"Logical line {logical_line_index} continues before its first segment."
                )
            rebuilt[logical_line_index] += LOGICAL_JOIN_SEPARATORS[join] + line["text"]
    return rebuilt


def validate_line_annotations(batch_dir: Path, manifest_payload: dict[str, Any]) -> int:
    """Validate ``line_annotations.json`` against the batch; return its line count."""

    path = batch_dir / LINE_ANNOTATIONS_FILENAME
    manifest_path = batch_dir / "generation_manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JSONDecodeError) as exc:
        raise LineAnnotationsError(f"Line annotations are not readable JSON: {path}: {exc}") from exc
    try:
        jsonschema.validate(payload, _line_annotations_schema())
    except jsonschema.ValidationError as exc:
        location = "/".join(str(part) for part in exc.absolute_path) or "<root>"
        raise LineAnnotationsError(f"Line annotations schema violation at {location}: {exc.message}") from exc

    if payload["generation_manifest_sha256"] != sha256_file(manifest_path):
        raise LineAnnotationsError("Line annotations generation_manifest_sha256 does not match the manifest file.")

    expected_pages = [
        (sample, page)
        for sample in manifest_payload["samples"]
        for page in sample["pages"]
    ]
    if len(payload["pages"]) != len(expected_pages):
        raise LineAnnotationsError(
            f"Line annotations cover {len(payload['pages'])} pages; manifest has {len(expected_pages)}."
        )
    line_count = 0
    for page_index, (annotated, (sample, page)) in enumerate(zip(payload["pages"], expected_pages, strict=True)):
        where = f"pages[{page_index}]"
        for key, expected in (
            ("sample_id", sample["sample_id"]),
            ("page_id", page["page_id"]),
            ("page_sha256", page["sha256"]),
            ("width", page["width"]),
            ("height", page["height"]),
        ):
            if annotated[key] != expected:
                raise LineAnnotationsError(f"{where}.{key} does not match the manifest: {annotated[key]!r}")
        _validate_page_lines(annotated, sample["text"]["logical_order"], where)
        line_count += len(annotated["lines"])
    return line_count


def _validate_page_lines(page: dict[str, Any], logical_order: str, where: str) -> None:
    lines = page["lines"]
    width, height = page["width"], page["height"]
    previous_logical_index = -1
    for position, line in enumerate(lines):
        line_where = f"{where}.lines[{position}]"
        if line["line_index"] != position:
            raise LineAnnotationsError(f"{line_where}.line_index must be {position}.")
        logical_line_index = line["logical_line_index"]
        if logical_line_index is None:
            if line["logical_join"] is not None:
                raise LineAnnotationsError(f"{line_where}.logical_join must be null outside logical_order.")
        else:
            if logical_line_index < previous_logical_index:
                raise LineAnnotationsError(f"{line_where}.logical_line_index must not decrease.")
            previous_logical_index = logical_line_index
        if unicodedata.normalize("NFC", line["text"]) != line["text"]:
            raise LineAnnotationsError(f"{line_where}.text must be NFC-normalized.")
        for key in ("polygon", "baseline"):
            for x, y in line[key]:
                if not (0 <= x < width and 0 <= y < height):
                    raise LineAnnotationsError(f"{line_where}.{key} point {[x, y]} is outside the page.")

    logical_lines = logical_order.split("\n")
    try:
        rebuilt = reconstruct_logical_lines(lines)
    except LineAnnotationsError as exc:
        raise LineAnnotationsError(f"{where}: {exc}") from exc
    if sorted(rebuilt) != list(range(len(logical_lines))):
        raise LineAnnotationsError(
            f"{where} lines must cover every logical_order line by logical_line_index."
        )
    for logical_line_index, text in rebuilt.items():
        if text != logical_lines[logical_line_index]:
            raise LineAnnotationsError(
                f"{where} lines for logical line {logical_line_index} rebuild {text!r}, "
                f"expected {logical_lines[logical_line_index]!r}."
            )


def _line_annotations_schema() -> dict[str, Any]:
    schema_path = resources.files("hocrsyngen") / "schemas" / "line_annotations.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))
