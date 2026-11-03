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
# Bidi controls must never reach line text: the page draw path relies on
# Pillow/raqm reordering logical-order text, not on embedded controls.
BIDI_CONTROL_CHARACTERS = frozenset("\u200e\u200f\u061c\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


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
        if document.lines is None or document.regions is None:
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
                    "truncated_segments": document.truncated_segments,
                    "lines": [
                        {
                            "line_index": line_index,
                            "logical_line_index": line.logical_line_index,
                            "logical_join": line.logical_join,
                            "occluded": line.occluded,
                            "region": line.region,
                            "region_index": line.region_index,
                            "text": line.text,
                            "polygon": [list(point) for point in line.polygon],
                            "baseline": [list(point) for point in line.baseline],
                        }
                        for line_index, line in enumerate(document.lines)
                    ],
                    "regions": [
                        {
                            "region_index": region.region_index,
                            "type": region.region_type,
                            "polygon": [list(point) for point in region.polygon],
                            "reading_order_index": region.reading_order_index,
                            "line_indices": list(region.line_indices),
                        }
                        for region in document.regions
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
    with_regions = {"regions" in page for page in payload["pages"]}
    if len(with_regions) > 1:
        raise LineAnnotationsError("Line annotations must give regions on every page or on none.")
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
        _validate_page_regions(annotated, where)
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
        text = line["text"]
        if unicodedata.normalize("NFC", text) != text:
            raise LineAnnotationsError(f"{line_where}.text must be NFC-normalized.")
        if text != text.strip():
            raise LineAnnotationsError(f"{line_where}.text must not have surrounding whitespace.")
        if any(unicodedata.category(character) == "Cc" or character in BIDI_CONTROL_CHARACTERS for character in text):
            raise LineAnnotationsError(f"{line_where}.text must not contain control or bidi control characters.")
        baseline_xs = [x for x, _y in line["baseline"]]
        if baseline_xs[0] >= baseline_xs[-1] or baseline_xs != sorted(baseline_xs):
            raise LineAnnotationsError(f"{line_where}.baseline must run left-to-right in pixel x.")
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


def _validate_page_regions(page: dict[str, Any], where: str) -> None:
    """Check S11a regions; sidecars written before S11a have none."""

    lines = page["lines"]
    if "regions" not in page:
        if any("region_index" in line for line in lines):
            raise LineAnnotationsError(f"{where} lines carry region_index but the page has no regions.")
        return
    regions = page["regions"]
    width, height = page["width"], page["height"]
    owner: dict[int, int] = {}
    reading_ordered: list[int] = []
    next_reading_order_index = 0
    for position, region in enumerate(regions):
        region_where = f"{where}.regions[{position}]"
        if region["region_index"] != position:
            raise LineAnnotationsError(f"{region_where}.region_index must be {position}.")
        for x, y in region["polygon"]:
            if not (0 <= x < width and 0 <= y < height):
                raise LineAnnotationsError(f"{region_where}.polygon point {[x, y]} is outside the page.")
        line_indices = region["line_indices"]
        if line_indices != sorted(set(line_indices)):
            raise LineAnnotationsError(f"{region_where}.line_indices must be strictly increasing.")
        members = []
        for line_index in line_indices:
            if not 0 <= line_index < len(lines) or line_index in owner:
                raise LineAnnotationsError(
                    f"{region_where}.line_indices names line {line_index}, which is missing or in another region."
                )
            owner[line_index] = position
            line = lines[line_index]
            if line.get("region_index") != position or line["region"] != region["type"]:
                raise LineAnnotationsError(
                    f"{region_where} line {line_index} must have region {region['type']!r} and region_index {position}."
                )
            if not polygon_contains(region["polygon"], line["polygon"]):
                raise LineAnnotationsError(f"{region_where}.polygon does not contain line {line_index}'s polygon.")
            members.append(line)
        in_order = any(line["logical_line_index"] is not None for line in members)
        expected_reading_order_index = next_reading_order_index if in_order else None
        if region["reading_order_index"] != expected_reading_order_index:
            raise LineAnnotationsError(
                f"{region_where}.reading_order_index must be {expected_reading_order_index!r}."
            )
        if in_order:
            if any(line["logical_line_index"] is None for line in members):
                raise LineAnnotationsError(f"{region_where} mixes lines inside and outside logical_order.")
            next_reading_order_index += 1
            reading_ordered.extend(line_indices)
    if sorted(owner) != list(range(len(lines))):
        raise LineAnnotationsError(f"{where} regions must contain every line exactly once.")
    # Reading regions in reading_order_index order and their lines in order
    # must walk the logical_order lines in line_index order.
    scored = [line["line_index"] for line in lines if line["logical_line_index"] is not None]
    if reading_ordered != scored:
        raise LineAnnotationsError(f"{where} region reading order disagrees with logical_order.")


def polygon_contains(outer: Sequence[Sequence[int]], inner: Sequence[Sequence[int]], tolerance: float = 1.0) -> bool:
    """True when every ``inner`` point lies in the convex ``outer`` polygon, within ``tolerance`` px."""

    edges = list(zip(outer, [*outer[1:], outer[0]]))
    # Orientation-free: a point is inside when it is on the same side of
    # every edge as the polygon's interior.
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in edges)
    sign = 1 if area > 0 else -1
    for x, y in inner:
        for (x0, y0), (x1, y1) in edges:
            length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            if length == 0:
                continue
            cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
            if sign * cross / length < -tolerance:
                return False
    return True


def _line_annotations_schema() -> dict[str, Any]:
    schema_path = resources.files("hocrsyngen") / "schemas" / "line_annotations.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))
