"""Optional hash-bound pre-photometric page pairs, in the final page frame."""
from __future__ import annotations

import json
import math
from pathlib import Path, PurePosixPath
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hocrsyngen.generator import SyntheticDocument
    from hocrsyngen.manifest import GenerationManifest

from PIL import Image, UnidentifiedImageError

from hocrsyngen.io import sha256_file

FILENAME = "paired_render.json"
SCHEMA = "hocrsyngen_paired_render.v1"


class PairedRenderError(ValueError):
    pass


def write_paired_render(manifest: GenerationManifest, documents: Sequence[SyntheticDocument],
                        manifest_path: Path) -> Path:
    docs = {d.sample_id: d for d in documents}
    pages = []
    for sample in manifest.samples:
        document = docs[sample.sample_id]
        pair = document.paired_asset
        if pair is None:
            raise PairedRenderError("Missing paired render")
        for page in sample.pages:
            pages.append({"sample_id": sample.sample_id, "page_id": page.page_id,
                "source_sha256": page.sha256, "pair_path": pair["path"],
                "pair_sha256": pair["sha256"], "width": page.width, "height": page.height,
                "generator_version": sample.generator_version,
                "degradation_preset": sample.provenance.degradation_preset,
                "parameters": {k: v for k, v in pair.items() if k not in ("path", "sha256")}})
    payload = {"schema": SCHEMA, "generation_manifest_sha256": sha256_file(manifest_path),
               "coordinate_space": "final_page_pixels", "pages": pages}
    path = manifest_path.parent / FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return path


def validate_paired_render(root: Path, manifest: dict[str, Any]) -> None:
    def fail(message):
        raise PairedRenderError(message)

    try:
        payload = json.loads((root / FILENAME).read_text(encoding="utf-8"),
                             parse_constant=lambda _: fail("Non-finite pair metadata"))
        if not isinstance(payload, dict) or set(payload) != {"schema", "generation_manifest_sha256", "coordinate_space", "pages"}:
            fail("Invalid paired render fields")
        if (payload["schema"] != SCHEMA or payload["coordinate_space"] != "final_page_pixels"
                or payload["generation_manifest_sha256"] != sha256_file(root / "generation_manifest.json")):
            fail("Paired render manifest binding mismatch")
        expected = {(s["sample_id"], p["page_id"]): (s, p)
                    for s in manifest["samples"] for p in s["pages"]}
        if not isinstance(payload["pages"], list) or len(payload["pages"]) != len(expected):
            fail("Paired render page coverage mismatch")
        seen, paths = set(), set()
        for item in payload["pages"]:
            fields = {"sample_id", "page_id", "source_sha256", "pair_path", "pair_sha256", "width", "height",
                      "generator_version", "degradation_preset", "parameters"}
            if not isinstance(item, dict) or set(item) != fields:
                fail("Invalid paired render page")
            key = (item["sample_id"], item["page_id"])
            if key not in expected or key in seen:
                fail("Unknown or duplicate paired render page")
            seen.add(key)
            sample, page = expected[key]
            if (item["source_sha256"] != page["sha256"] or item["width"] != page["width"]
                    or item["height"] != page["height"] or item["generator_version"] != sample["generator_version"]
                    or item["degradation_preset"] != sample["provenance"]["degradation_preset"]):
                fail("Paired render page binding mismatch")
            path = item["pair_path"]
            if not isinstance(path, str) or not path or "\\" in path:
                fail("Invalid paired render path")
            rel = PurePosixPath(path)
            if rel.is_absolute() or any(part in (".", "..") for part in path.split("/")):
                fail("Invalid paired render path")
            asset = (root / path).resolve()
            if not asset.is_relative_to(root.resolve()) or asset in paths:
                fail("Invalid or duplicate paired render asset")
            paths.add(asset)
            if not asset.is_file() or sha256_file(asset) != item["pair_sha256"]:
                fail("Paired render asset hash mismatch")
            with Image.open(asset) as im:
                if im.format != "PNG" or im.size != (page["width"], page["height"]):
                    fail("Paired render asset dimensions or format mismatch")
                im.verify()
            params = item["parameters"]
            required = {"rotation_degrees", "blur_radius", "grain_passes", "grain_alpha", "contrast", "brightness", "jpeg_quality"}
            if not isinstance(params, dict) or set(params) != required:
                fail("Invalid paired render parameters")
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in params.values()):
                fail("Invalid paired render parameter value")
            if (type(params["grain_passes"]) is not int or params["grain_passes"] < 0
                    or type(params["jpeg_quality"]) is not int or not 1 <= params["jpeg_quality"] <= 100
                    or any(params[k] < 0 for k in ("blur_radius", "grain_alpha", "contrast", "brightness"))):
                fail("Invalid paired render parameter range")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError, UnidentifiedImageError) as exc:
        raise PairedRenderError("Invalid paired render sidecar or asset") from exc
