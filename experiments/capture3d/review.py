# SPDX-License-Identifier: CC0-1.0
"""Screen paired captures with exact OCR and assemble an entirely local gallery."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from html import escape
from io import BytesIO
from math import ceil, floor
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unicodedata

import cv2
import numpy as np
from PIL import Image

from .batch import checked_file, json_write, open_rgb, rejected_pairs, sha
from .geometry import Paper, distort


BIDI = dict.fromkeys((0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)))


def normalise(text):
    return " ".join(unicodedata.normalize("NFC", text).translate(BIDI).split())


def projection_map(paper, matrix, source_size, image_size, k1):
    """Map rectified pixel centres through the same triangular mesh and shutter-centre lens."""
    nx, ny = paper.divisions
    sw, sh = source_size
    width, height = image_size
    u = (np.arange(sw) + .5) * nx / sw
    v = (np.arange(sh) + .5) * ny / sh
    cx, ry = np.floor(u).astype(int), np.floor(v).astype(int)
    xx, yy = np.meshgrid(u - cx, v - ry, indexing="xy")
    x, y = np.meshgrid(cx, ry, indexing="xy")
    vertices = np.asarray(paper.mesh()[0]).reshape(ny + 1, nx + 1, 3)
    lower, upper = np.minimum(xx, yy), np.maximum(xx, yy)
    middle = np.where((xx >= yy)[..., None], vertices[y, x + 1], vertices[y + 1, x])
    points = ((1 - upper)[..., None] * vertices[y, x] + (upper - lower)[..., None] * middle
              + lower[..., None] * vertices[y + 1, x + 1])
    matrix = np.asarray(matrix)
    clip = points @ matrix[[0, 1, 3], :3].T + matrix[[0, 1, 3], 3]
    px = (clip[..., 0] / clip[..., 2] + 1) * width / 2
    py = (1 - clip[..., 1] / clip[..., 2]) * height / 2
    mx, my = distort(px, py, width, height, k1)
    return (mx - .5).astype(np.float32), (my - .5).astype(np.float32)


def tesseract(image, model, directory, psm):
    data = BytesIO()
    Image.fromarray(image).save(data, format="PNG")
    command = ["tesseract", "stdin", "stdout", "-l", model, "--psm", str(psm), "--dpi", "240"]
    if directory:
        command.extend(("--tessdata-dir", str(directory)))
    result = subprocess.run(command, input=data.getvalue(), capture_output=True, check=True, timeout=20)
    text = result.stdout.decode()
    if psm == 6:
        return tuple(filter(None, map(normalise, text.splitlines())))
    return normalise(text)


def line_crop(rectified, bounds):
    x, y, right, bottom = bounds
    return rectified[max(0, floor(y) - 12):ceil(bottom) + 12, max(0, floor(x) - 17):ceil(right) + 17]


def equalise_paper(gray):
    """Compensate for smooth illumination during transcription, using only captured pixels."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))
    paper = cv2.GaussianBlur(cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel), (0, 0), 3.0)
    delta = np.maximum(0, paper.astype(np.float32) - gray)
    return np.rint(255 - np.minimum(255, 382.5 * delta / np.maximum(paper, 44))).astype(np.uint8)


def tesseract_votes(rectified, equalised, lines, model, path, pool):
    gold = tuple(normalise(line["text"]) for line in lines)
    if tesseract(rectified, model, path, 6) == gold:
        return [True] * len(lines)
    if tesseract(equalised, model, path, 6) == gold:
        return [True] * len(lines)

    def exact(line, expected):
        return any(tesseract(line_crop(view, line["bbox"]), model, path, 7) == expected
                   for view in (rectified, equalised))

    return list(pool.map(exact, lines, gold))


def kraken_votes(pending, executable, weights, scratch):
    for start in range(0, len(pending), 72):
        group = pending[start:start + 72]
        command = [executable, "-d", "cpu", "-r", "--threads", "1"]
        readings = []
        for i, (image, expected, line_votes) in enumerate(group, start):
            source, destination = scratch / f"{i}.png", scratch / f"{i}.txt"
            Image.fromarray(image).save(source)
            command.extend(("-i", str(source), str(destination)))
            readings.append((destination, expected, line_votes))
        command.extend(("ocr", "-s", "-m", str(weights), "--base-dir", "R", "--num-line-workers", "0"))
        subprocess.run(command, capture_output=True, check=True, timeout=240)
        for path, gold, votes in readings:
            votes["kraken"] = normalise(path.read_text()) == gold


def check_labels(captures, root, sources, tessdata, kraken, weights, scratch):
    votes = {}
    pending = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for index in range(0, len(captures), 2):
            pair = captures[index:index + 2]
            first = pair[0]
            lines = [line for line in first["annotations"] if line["kind"] == "line"]
            source_size = sources[first["pair_id"]]
            geometry = Paper(**first["paper"]), first["clip_from_sheet"], source_size
            for row in pair:
                img = open_rgb(checked_file(root, row["image"], row["image_sha256"]))
                if row is first:
                    coords = projection_map(*geometry, img.shape[:2][::-1], row["phone"]["k1"])
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                rect = cv2.remap(gray, *coords, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                equalised = equalise_paper(rect)
                heb = tesseract_votes(rect, equalised, lines, "heb", None, pool)
                modern = tesseract_votes(rect, equalised, lines, "heocr_modern_v1", tessdata, pool)
                decisions = {}
                for i, line in enumerate(lines):
                    decisions[line["id"]] = {"tesseract_heb": heb[i], "heocr_modern_v1": modern[i]}
                    if kraken and heb[i] != modern[i]:
                        pending.append((line_crop(equalised, line["bbox"]).copy(), normalise(line["text"]), decisions[line["id"]]))
                votes[row["id"]] = decisions
            print(f"Guarded {first['pair_id']} ({sum(sum(row.values()) == 2 for row in votes[pair[1]['id']].values())}/{len(lines)} lines dual-exact before arbitration)", flush=True)
    if pending:
        kraken_votes(pending, kraken, weights, scratch)
    return votes


def features(row):
    recipe = row["realism"]
    camera = recipe["camera"]
    effects = {name for name, key in (("noise", "noise_strength"), ("flash", "flash_w"),
                                       ("motion", "motion_m"), ("defocus", "fstop")) if camera[key]}
    return {("scene", row["scene"]), ("paper", recipe["paper"]["stock"]), ("page", row["source_sha256"]),
            ("light", recipe["lighting"]["profile"]), ("fold", recipe["fold"]["profile"]),
            *(('effect', name) for name in effects or {'clean control'}), ("combination", tuple(sorted(effects)))}


def choose_pairs(eligible, count):
    """Prefer visual coverage, with deterministic tie-breaking in source order."""
    remaining = list(eligible)
    picked = set()
    seen = Counter()
    weights = {"scene": 7, "paper": 5, "light": 5, "fold": 5, "effect": 7, "combination": 2, "page": 4}
    while remaining and len(picked) < count:
        ix = max(range(len(remaining)), key=lambda k: sum(weights[tag[0]] / (1 + seen[tag]) ** 2
                                                          for tag in features(remaining[k][1])))
        pair = remaining.pop(ix)
        picked.add(pair[0]["pair_id"])
        seen.update(features(pair[1]))
    return [pair for pair in eligible if pair[0]["pair_id"] in picked]


def parameters(row):
    recipe, paper, phone = row["realism"], row["paper"], row["phone"]
    light = recipe["lighting"]
    folds = [f"{paper[key] * 1000:.0f} mm {name}" for name, key in (("fold valley", "valley_depth"),
             ("crease ridge", "crease_height"), ("crumple", "crumple")) if paper[key] > .005]
    if paper["dogear_size"]:
        folds.append(f"{paper['dogear_size'] * 1000:.0f} mm dog-ear at {paper['dogear_angle_deg']:.0f}°")
    effects = []
    if phone["noise_strength"]:
        effects.append(f"Sensor noise at ISO {phone['iso']} (×{phone['noise_strength']:.2f})")
    if phone.get("flash"):
        effects.append(f"Near-lens flash spot at {phone['flash']['power_w']:.1f} W")
    if phone["shutter_drift_m"]:
        effects.append(f"Motion blur {phone['shutter_drift_m'] * 1000:.1f} mm drift at {phone['motion_angle_deg']:.0f}°")
    if phone["defocus_enabled"]:
        effects.append(f"Defocus f/{phone['fstop_equivalent']:.1f}, {phone['focus_offset_m'] * 100:+.1f} cm")
    return {"Paper": recipe["paper"]["stock"],
            "Folds": ", ".join([recipe["fold"]["profile"], *folds]),
            "Light": ", ".join([light["profile"], *(f"{s['name']} {s['power']:g} W" for s in light["sources"])]),
            "Shared camera": f"{phone['lens_mm_equivalent']:.1f} mm, roll {phone['roll_deg']:+.1f}°, exposure {phone['exposure_ev']:+.2f} EV",
            "Clean": "No added camera artefacts",
            "Treated": ", ".join(effects) if effects else "No added camera artefacts (control)"}


def gallery_html(pairs):
    cards = []
    for clean, treated in pairs:
        title = f"{clean['scene'].title()} · {clean['pair_id'].split('-')[-1]}"
        figures = []
        for row, caption in ((clean, "Clean capture"), (treated, "Camera artefacts" if any(
                tag[0] == "effect" and tag[1] != "clean control" for tag in features(treated)) else "Clean control")):
            image = escape(row["image"])
            figures.append(f'<figure><figcaption>{caption}</figcaption><a href="{image}"><img loading="lazy" '
                           f'alt="{escape(title)} · {caption}" src="{image}"></a></figure>')
        settings = "".join(f"<dt>{escape(key)}</dt><dd>{escape(value)}</dd>" for key, value in parameters(treated).items())
        cards.append(f'<article><h2>{escape(title)}</h2><div class="grid">{"".join(figures)}'
                     f'<aside><h3>Parameters</h3><dl>{settings}</dl></aside></div></article>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HeOCR · 3D Capture v2</title><style>
*{box-sizing:border-box}body{max-width:94rem;padding:0 1.5rem;margin:2.5rem auto;background:#eeebe4;color:#22231f;
font:16px/1.5 system-ui,sans-serif}h1{font-size:2.4rem;margin-bottom:.25rem}p{margin-top:0;color:#484a40}
article{border-top:1px solid #c8c5ba;padding:1rem 0 1.6rem}h2{margin:0 0 .85rem;font-size:1.25rem}h3{margin:0;font-size:1rem}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(13rem,.67fr);gap:1rem;align-items:start}
figure{margin:0}figcaption{font-size:.9rem;margin-bottom:.45rem}img{display:block;width:100%;height:auto;border-radius:4px}
aside{background:#f7f5ef;border-radius:4px;padding:1rem}dl{margin:.5rem 0 0}dt{font-weight:650}dd{margin:0 0 .63em}
@media(max-width:780px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}aside{grid-column:1/-1}}
</style><body><h1>HeOCR · 3D capture v2</h1><p>Each pair shares the same scene, light, folds, paper and shutter-centre viewpoint.</p>
''' + "\n".join(cards) + "</body></html>\n"


def review(batch, output, tessdata, kraken, weights, count):
    manifest_path = batch / "generation_manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["schema"] != "heocr.capture3d.paired.v2" or output.exists():
        raise ValueError("Expected a paired run and a fresh local output directory")
    captures = manifest.pop("renders")
    if rejected_pairs(captures):
        raise ValueError("The batch retained a pair with a failed visibility check")
    sources = {}
    for row in captures[::2]:
        with Image.open(checked_file(batch, row["source_image"], row["source_sha256"])) as source:
            sources[row["pair_id"]] = source.size
    with TemporaryDirectory(prefix=".capture-ocr-", dir=batch.parent.resolve()) as scratch:
        votes = check_labels(captures, batch, sources, tessdata, kraken, weights, Path(scratch))
    eligible, rejected = [], []
    for i in range(0, len(captures), 2):
        clean, treated = captures[i:i + 2]
        failures = {row["arm"]: [ident for ident, readers in votes[row["id"]].items() if sum(readers.values()) < 2]
                    for row in (clean, treated)}
        if any(failures.values()):
            rejected.append({"pair_id": clean["pair_id"], "failed_lines": failures})
        else:
            eligible.append((clean, treated))
    print(f"{len(eligible)}/{len(captures) // 2} ground-truth-valid pairs pass the label guard", flush=True)
    if len(eligible) < count:
        raise ValueError(f"Only {len(eligible)} readable pairs for a {count}-pair gallery: {rejected}")
    selected = choose_pairs(eligible, count)
    (output / "images").mkdir(parents=True)
    for pair in selected:
        for row in pair:
            path = checked_file(batch, row["image"], row["image_sha256"])
            row["image"] = f"images/{path.name}"
            shutil.copyfile(path, output / row["image"])
            row.pop("source_image")
            row["line_reader_votes"] = votes[row["id"]]
    (output / "index.html").write_text(gallery_html(selected), encoding="utf-8")
    readers = {"heocr_modern_v1_sha256": sha(tessdata / "heocr_modern_v1.traineddata")}
    heb = Path(os.environ.get("TESSDATA_PREFIX", ".")) / "heb.traineddata"
    if heb.is_file():
        readers["tesseract_heb_sha256"] = sha(heb)
    if weights:
        readers["kraken_sha256"] = sha(weights)
    manifest.update(batch_manifest_sha256=sha(manifest_path), selected_pairs=[list(pair) for pair in selected],
                    ocr_rejected_pairs=rejected, ocr_passed_pair_count=len(eligible),
                    reader_models=readers, index_sha256=sha(output / "index.html"))
    json_write(output / "gallery_manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch", "output", "tessdata"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--kraken")
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--count", type=int, default=15)
    args = parser.parse_args()
    if bool(args.kraken) != bool(args.weights) or args.count < 1:
        parser.error("Supply both Kraken paths and a positive pair count")
    cv2.setNumThreads(1)
    review(**vars(args))


if __name__ == "__main__":
    main()
