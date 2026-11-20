"""Derive a hash-bound phone capture batch from annotated synthetic pages."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from hocrsyngen.io import sha256_file
from hocrsyngen.line_annotations import LINE_ANNOTATIONS_FILENAME
from hocrsyngen.paired_render import FILENAME as PAIRED_FILENAME
from hocrsyngen.validation import MANIFEST_FILENAME, validate_batch

from .geometry import transform_annotation
from .pipeline import capture, validate_config


CAPTURE_FILENAME = "capture_annotations.json"
CAPTURE_SCHEMA = "hocrsyngen_phone_capture_annotations.v1"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                               separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")


def capture_batch(source, output, *, seed, config, allow_source_jpeg=False):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"Output already exists: {output}")
    if not (source / LINE_ANNOTATIONS_FILENAME).is_file():
        raise ValueError("Input needs generate --emit-line-annotations")
    if (source / CAPTURE_FILENAME).exists() or (source / "glyph_provenance.json").exists():
        raise ValueError("Input must be a procedural generator batch with v1 line annotations")
    if not allow_source_jpeg and not (source / PAIRED_FILENAME).is_file():
        raise ValueError("Input needs generate --emit-paired-render or explicit --allow-source-jpeg")
    validate_config(config)
    validate_batch(source)
    manifest_path = source / MANIFEST_FILENAME
    annotation_path = source / LINE_ANNOTATIONS_FILENAME
    manifest = _read(manifest_path)
    source_manifest_sha = sha256_file(manifest_path)
    source_annotations_sha = sha256_file(annotation_path)
    annotations = _read(annotation_path)
    pair_path = source / PAIRED_FILENAME
    pairs = {
        (p["sample_id"], p["page_id"]): p for p in _read(pair_path)["pages"]
    } if pair_path.is_file() else {}
    pages = [(sample["sample_id"], page) for sample in manifest["samples"] for page in sample["pages"]]
    keys = {(sample_id, page["page_id"]) for sample_id, page in pages}
    if len(keys) != len(pages):
        raise ValueError("Input sample/page keys must be unique")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".scanifier-", dir=output.parent) as scratch:
        stage = Path(scratch) / "batch"
        (stage / "assets").mkdir(parents=True)
        captures = []
        for index, ((sample_id, page), annotation) in enumerate(zip(pages, annotations["pages"], strict=True)):
            key = (sample_id, page["page_id"])
            digest = hashlib.sha256(json.dumps((seed, *key), ensure_ascii=False).encode()).digest()
            page_seed = int.from_bytes(digest[:8], "big")
            pair = pairs.get(key)
            raster_path = pair["pair_path"] if pair else page["asset_path"]
            raster_hash = pair["pair_sha256"] if pair else page["sha256"]
            with Image.open(source / raster_path) as image:
                result = capture(image, page_seed, config)
            relative = f"assets/{index:06d}.jpg"
            (stage / relative).write_bytes(result.jpeg)
            sha = hashlib.sha256(result.jpeg).hexdigest()
            width, height = result.warp.size
            captured = {
                **annotation, "width": width, "height": height, "page_sha256": sha,
                "lines": [transform_annotation(line, result.warp) for line in annotation["lines"]],
                "source_raster_sha256": raster_hash,
                "source_page_sha256": annotation["page_sha256"],
                "source_raster": "paired_png" if pair else "manifest_jpeg",
                "seed": page_seed, "input_exif_orientation": result.input_orientation,
                "parameters": result.parameters, "warp": result.warp.record(),
            }
            if "regions" in annotation:
                captured["regions"] = [transform_annotation(region, result.warp) for region in annotation["regions"]]
            captures.append(captured)
            page.update(asset_path=relative, sha256=sha, width=width, height=height)

        _write(stage / MANIFEST_FILENAME, manifest)
        _write(stage / CAPTURE_FILENAME, {
            "schema": CAPTURE_SCHEMA, "coordinate_space": "final_page_pixel_edges",
            "generation_manifest_sha256": sha256_file(stage / MANIFEST_FILENAME),
            "source_generation_manifest_sha256": source_manifest_sha,
            "source_line_annotations_sha256": source_annotations_sha,
            "seed": seed, "config": config, "pages": captures,
        })
        # Reserve the output exclusively after the batch is ready. The rename
        # then publishes the complete directory on the same filesystem.
        output.mkdir()
        try:
            stage.replace(output)
        except OSError:
            output.rmdir()
            raise
