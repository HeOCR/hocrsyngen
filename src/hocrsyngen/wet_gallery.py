from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from hocrsyngen.validation import validate_batch


WET_GALLERY_REPORT_VERSION = "wet_gallery_report.v1"
WET_GALLERY_INDEX_FILENAME = "index.html"
WET_TEST_RUN_FILENAME = "wet_test_run.json"


@dataclass(frozen=True)
class WetGalleryResult:
    run_root: Path
    output_dir: Path
    index_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class GalleryBatch:
    batch_id: str
    role: str
    batch_path: str
    manifest_path: str


@dataclass(frozen=True)
class GalleryPage:
    batch_id: str
    batch_role: str
    sample_id: str
    page_id: str
    template_id: str
    recipe_id: str
    persona: str | None
    condition: str | None
    degradation: str
    font_id: str
    logical_text: str
    asset_path: str
    image_href: str
    full_image_href: str
    width: int
    height: int


def create_wet_gallery(*, run_root: Path, output: Path) -> WetGalleryResult:
    run_root = run_root.resolve()
    output = output.resolve()
    if not run_root.is_dir():
        raise ValueError(f"wet-test run directory does not exist: {run_root}")
    try:
        output.relative_to(run_root)
    except ValueError as exc:
        raise ValueError("gallery output directory must be inside the wet-test run") from exc
    if output.exists() and not output.is_dir():
        raise ValueError(f"gallery output path exists and is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        raise ValueError(
            f"gallery output directory already exists and is not empty: {output}"
        )

    run_payload = _load_wet_test_run(run_root)
    batches = _gallery_batches(run_payload)
    pages: list[GalleryPage] = []
    for batch in batches:
        batch_dir = _resolve_run_path(run_root, batch.batch_path)
        validate_batch(batch_dir)
        manifest_path = _resolve_run_path(run_root, batch.manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        pages.extend(
            _gallery_pages(
                run_root=run_root,
                output=output,
                batch=batch,
                manifest=manifest,
            )
        )

    output.mkdir(parents=True, exist_ok=True)
    index_path = output / WET_GALLERY_INDEX_FILENAME
    index_path.write_text(
        _render_gallery_html(run_payload=run_payload, pages=pages),
        encoding="utf-8",
    )
    payload: dict[str, Any] = {
        "report_version": WET_GALLERY_REPORT_VERSION,
        "run_path": ".",
        "index_path": _relative_path(run_root, index_path),
        "page_count": len(pages),
        "sample_count": len(pages),
        "batch_count": len(batches),
        "scope": {
            "generator_quality_evidence_only": True,
            "release_ready_dataset_artifact": False,
            "manifest_v1_changed": False,
            "hocrgen_behavior_added": False,
            "human_review_sidecar_included": False,
            "llm_triage_included": False,
            "network_required": False,
        },
    }
    return WetGalleryResult(
        run_root=run_root,
        output_dir=output,
        index_path=index_path,
        payload=payload,
    )


def _load_wet_test_run(run_root: Path) -> dict[str, Any]:
    path = run_root / "reports" / WET_TEST_RUN_FILENAME
    if not path.is_file():
        raise ValueError(f"missing wet-test run report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("report_version") != "wet_test_run.v1":
        raise ValueError("wet-gallery requires a wet_test_run.v1 report")
    if payload.get("status") != "passed":
        raise ValueError("wet-gallery requires a passed wet-test run")
    return payload


def _gallery_batches(run_payload: dict[str, Any]) -> list[GalleryBatch]:
    generated_batch = run_payload.get("generated_batch")
    if not isinstance(generated_batch, dict):
        raise ValueError("wet-test run report is missing generated_batch")
    batches = [
        GalleryBatch(
            batch_id=str(generated_batch.get("batch_id", "generated_batch")),
            role=str(generated_batch.get("role", "generated_batch")),
            batch_path=_portable_relative_str(generated_batch.get("batch_path")),
            manifest_path=_portable_relative_str(generated_batch.get("manifest_path")),
        )
    ]
    supplemental_batches = run_payload.get("supplemental_batches", [])
    if not isinstance(supplemental_batches, list):
        raise ValueError("wet-test run report supplemental_batches must be a list")
    for index, raw_batch in enumerate(supplemental_batches):
        if not isinstance(raw_batch, dict):
            raise ValueError("wet-test run report supplemental batch must be an object")
        batches.append(
            GalleryBatch(
                batch_id=str(raw_batch.get("batch_id", f"supplemental_{index}")),
                role=str(raw_batch.get("role", "supplemental")),
                batch_path=_portable_relative_str(raw_batch.get("batch_path")),
                manifest_path=_portable_relative_str(raw_batch.get("manifest_path")),
            )
        )
    return batches


def _gallery_pages(
    *,
    run_root: Path,
    output: Path,
    batch: GalleryBatch,
    manifest: dict[str, Any],
) -> list[GalleryPage]:
    samples = manifest.get("samples", [])
    if not isinstance(samples, list):
        raise ValueError(f"manifest samples must be a list: {batch.manifest_path}")
    pages: list[GalleryPage] = []
    batch_path = PurePosixPath(batch.batch_path)
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError(f"manifest sample must be an object: {batch.manifest_path}")
        provenance = sample.get("provenance", {})
        controls = sample.get("controls", {})
        text = sample.get("text", {})
        sample_pages = sample.get("pages", [])
        if not isinstance(provenance, dict) or not isinstance(controls, dict):
            raise ValueError(f"manifest sample metadata is invalid: {batch.manifest_path}")
        if not isinstance(text, dict) or not isinstance(sample_pages, list):
            raise ValueError(f"manifest sample content is invalid: {batch.manifest_path}")
        for page in sample_pages:
            if not isinstance(page, dict):
                raise ValueError(f"manifest page must be an object: {batch.manifest_path}")
            asset_path = _portable_relative_str(page.get("asset_path"))
            run_asset_path = batch_path / asset_path
            asset_abs = _resolve_run_path(run_root, run_asset_path.as_posix())
            image_href = _relative_href(output, asset_abs)
            pages.append(
                GalleryPage(
                    batch_id=batch.batch_id,
                    batch_role=batch.role,
                    sample_id=str(sample.get("sample_id", "")),
                    page_id=str(page.get("page_id", "")),
                    template_id=str(provenance.get("template_id", "")),
                    recipe_id=str(provenance.get("recipe_id", sample.get("recipe_id", ""))),
                    persona=controls.get("persona"),
                    condition=controls.get("condition"),
                    degradation=str(provenance.get("degradation_preset", "")),
                    font_id=str(provenance.get("font_id", "")),
                    logical_text=str(text.get("logical_order", "")),
                    asset_path=run_asset_path.as_posix(),
                    image_href=image_href,
                    full_image_href=image_href,
                    width=int(page.get("width", 0)),
                    height=int(page.get("height", 0)),
                )
            )
    return sorted(
        pages,
        key=lambda page: (page.batch_id, page.sample_id, page.page_id, page.asset_path),
    )


def _render_gallery_html(
    *, run_payload: dict[str, Any], pages: list[GalleryPage]
) -> str:
    run_profile = str(run_payload.get("profile", "unknown"))
    run_status = str(run_payload.get("status", "unknown"))
    seed = run_payload.get("config", {}).get("seed", "")
    cards = "\n".join(_render_page_card(page) for page in pages)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hocrsyngen wet-test gallery</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2933;
      background: #f7f7f4;
    }}
    header {{
      padding: 24px;
      border-bottom: 1px solid #d8d6cf;
      background: #ffffff;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 12px;
      color: #4b5563;
      font-size: 14px;
    }}
    main {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
      padding: 20px;
    }}
    article {{
      background: #ffffff;
      border: 1px solid #d8d6cf;
      border-radius: 8px;
      overflow: hidden;
    }}
    figure {{
      margin: 0;
      padding: 12px;
      background: #eef1f2;
      border-bottom: 1px solid #d8d6cf;
    }}
    img {{
      display: block;
      width: 100%;
      height: auto;
      max-height: 420px;
      object-fit: contain;
      background: #ffffff;
    }}
    .meta {{
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 6px 12px;
      padding: 12px;
      font-size: 13px;
    }}
    .meta dt {{
      color: #52616b;
      font-weight: 600;
    }}
    .meta dd {{
      margin: 0;
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .text {{
      direction: rtl;
      unicode-bidi: plaintext;
      padding: 12px;
      border-top: 1px solid #d8d6cf;
      font-size: 18px;
      line-height: 1.5;
      background: #fffdfa;
    }}
    a {{
      color: #005f73;
    }}
  </style>
</head>
<body>
  <header>
    <h1>hocrsyngen wet-test gallery</h1>
    <div class="summary">
      <span>profile: {html.escape(run_profile)}</span>
      <span>status: {html.escape(run_status)}</span>
      <span>seed: {html.escape(str(seed))}</span>
      <span>pages: {len(pages)}</span>
    </div>
  </header>
  <main>
{cards}
  </main>
</body>
</html>
"""


def _render_page_card(page: GalleryPage) -> str:
    rows = [
        ("batch id", page.batch_id),
        ("batch role", page.batch_role),
        ("sample id", page.sample_id),
        ("page id", page.page_id),
        ("template id", page.template_id),
        ("recipe id", page.recipe_id),
        ("style/persona", page.persona or "default"),
        ("condition", page.condition or "default"),
        ("degradation", page.degradation),
        ("font id", page.font_id),
        ("asset path", page.asset_path),
        ("dimensions", f"{page.width} x {page.height}"),
    ]
    meta = "\n".join(
        f"      <dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        for label, value in rows
    )
    image_href = html.escape(page.image_href, quote=True)
    full_image_href = html.escape(page.full_image_href, quote=True)
    return f"""    <article>
      <figure>
        <a href="{full_image_href}"><img src="{image_href}" alt="Generated page {html.escape(page.page_id, quote=True)} for sample {html.escape(page.sample_id, quote=True)}"></a>
      </figure>
      <dl class="meta">
{meta}
      </dl>
      <div class="text" lang="he">{html.escape(page.logical_text)}</div>
    </article>"""


def _resolve_run_path(run_root: Path, relative_path: str) -> Path:
    portable = PurePosixPath(_portable_relative_str(relative_path))
    resolved = (run_root / Path(*portable.parts)).resolve()
    try:
        resolved.relative_to(run_root)
    except ValueError as exc:
        raise ValueError(f"path escapes wet-test run root: {relative_path}") from exc
    return resolved


def _portable_relative_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("expected a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"expected a portable relative path: {value}")
    return path.as_posix()


def _relative_path(root: Path, path: Path) -> str:
    return PurePosixPath(*path.resolve().relative_to(root).parts).as_posix()


def _relative_href(from_dir: Path, target: Path) -> str:
    relative = os.path.relpath(target.resolve(), start=from_dir.resolve())
    path = PurePosixPath(*Path(relative).parts)
    if path.is_absolute() or "\\" in path.as_posix():
        raise ValueError(f"could not create relative gallery link for: {target}")
    return path.as_posix()
