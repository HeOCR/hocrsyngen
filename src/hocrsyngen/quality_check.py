"""Report recorded candidate-page quality signals without making release claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hocrsyngen.line_annotations import LINE_ANNOTATIONS_FILENAME
from hocrsyngen.validation import validate_batch

LIMITATION = (
    "Recorded flags are incomplete diagnostics, not a quality or release decision; "
    "main-flow text overlaps are not detected and zero flags do not prove visibility. "
    "Schema and hash binding do not authenticate annotation truth."
)


def _threshold(value: int | None, name: str) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f"{name} must be a non-negative integer or None")


def quality_check(
    batch_dir: Path, *, max_truncated_segments: int | None = None,
    max_occluded_lines: int | None = None,
) -> dict[str, Any]:
    """Validate and summarize an annotated batch; explicit limits are count ceilings."""
    _threshold(max_truncated_segments, "max_truncated_segments")
    _threshold(max_occluded_lines, "max_occluded_lines")
    batch_dir = Path(batch_dir)
    manifest_path = batch_dir / "generation_manifest.json"
    annotations_path = batch_dir / LINE_ANNOTATIONS_FILENAME
    if not annotations_path.is_file():
        raise ValueError("quality-check requires line_annotations.json")
    # Bind the report to the same files that are validated; fail if either
    # changes between validation and the subsequent read.
    before = (manifest_path.read_bytes(), annotations_path.read_bytes())
    validate_batch(batch_dir)
    after = (manifest_path.read_bytes(), annotations_path.read_bytes())
    if before != after:
        raise ValueError("batch manifest or annotations changed during quality-check")
    manifest, annotations = (json.loads(blob) for blob in after)
    template_by_sample = {s["sample_id"]: s["provenance"]["template_id"] for s in manifest["samples"]}
    templates: dict[str, dict[str, int]] = {}
    pages = []
    for page in annotations["pages"]:
        template = template_by_sample[page["sample_id"]]
        truncated = page["truncated_segments"]
        occluded = sum(line["occluded"] for line in page["lines"])
        stats = templates.setdefault(template, {"page_count": 0, "line_count": 0,
            "truncated_segments": 0, "occluded_lines": 0,
            "pages_with_truncation": 0, "pages_with_occlusion": 0})
        stats["page_count"] += 1
        stats["line_count"] += len(page["lines"])
        stats["truncated_segments"] += truncated
        stats["occluded_lines"] += occluded
        stats["pages_with_truncation"] += int(truncated > 0)
        stats["pages_with_occlusion"] += int(occluded > 0)
        if truncated or occluded:
            pages.append({"sample_id": page["sample_id"], "page_id": page["page_id"],
                "template_id": template, "truncated_segments": truncated, "occluded_lines": occluded,
                "warning_ids": (["truncated_segments"] if truncated else []) + (["occluded_lines"] if occluded else [])})
    keys = ("page_count", "line_count", "truncated_segments", "occluded_lines",
            "pages_with_truncation", "pages_with_occlusion")
    totals = {key: sum(value[key] for value in templates.values()) for key in keys}
    limits = {"max_truncated_segments": max_truncated_segments, "max_occluded_lines": max_occluded_lines}
    exceeded = (["truncated_segments"] if max_truncated_segments is not None and totals["truncated_segments"] > max_truncated_segments else [])
    if max_occluded_lines is not None and totals["occluded_lines"] > max_occluded_lines:
        exceeded.append("occluded_lines")
    return {"schema_version": "hocrsyngen_quality_check.v1",
        "manifest_sha256": hashlib.sha256(after[0]).hexdigest(),
        "line_annotations_sha256": hashlib.sha256(after[1]).hexdigest(),
        "coverage": "no_pages" if totals["page_count"] == 0 else "all_manifest_pages",
        "totals": totals, "by_template": dict(sorted(templates.items())),
        "affected_pages": sorted(pages, key=lambda p: (p["sample_id"], p["page_id"])),
        "thresholds": limits, "exceeded": exceeded, "limitation": LIMITATION}
