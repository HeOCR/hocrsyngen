# SPDX-License-Identifier: CC0-1.0
"""Drive headless Blender and package rendered phone JPEGs with exact text polygons."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .geometry import undistort
from .photometry import PhonePhotometry
from .realism import plan_realism
from .strong_folds import PROFILES
from .rounded_folds import PROFILES as ROUNDED_PROFILES


SCENES = {"desk", "floor", "book", "letter"}
MARKERS = ((.24, .20), (.69, .24), (.31, .47), (.72, .52), (.27, .76), (.68, .80))
IDENTITY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*")
SHA256 = re.compile(r"[0-9a-f]{64}")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def checked_file(root, name, expected):
    relative = Path(name)
    path = (root / relative).resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root.resolve()):
        raise ValueError(f"Expected a relative input file inside the manifest directory: {name}")
    if sha(path) != expected:
        raise ValueError(f"Input hash changed: {name}")
    return path


def source_rows(manifest):
    source = json.loads(manifest.read_bytes())
    if source.get("split") != "train-calibration" or not all(
        SHA256.fullmatch(source.get(key, "")) for key in ("text_gate_sha256", "fonts_guard_sha256")
    ):
        raise ValueError("Provide screened TRAIN/calibration text and font guard pins")
    used_ids = set()
    for row in source["pages"]:
        ident = row["id"]
        if not IDENTITY.fullmatch(ident) or ident in used_ids or row["scene"] not in SCENES:
            raise ValueError("Invalid or duplicate case ID or scene")
        if not SHA256.fullmatch(row.get("font_sha256", "")):
            raise ValueError(f"Missing font pin for {ident}")
        used_ids.add(ident)
        path = checked_file(manifest.parent, row["image"], row["sha256"])
        with Image.open(path) as page:
            width, height = page.size
        if not row["annotations"] or not (100 <= width <= 6000 and 100 <= height <= 6000):
            raise ValueError(f"Invalid page geometry or empty annotations for {ident}")
        object_ids = set()
        lines, words = {}, {}
        for annotation in row["annotations"]:
            x1, y1, x2, y2 = annotation["bbox"]
            text = annotation["text"]
            if (not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height) or not text
                    or unicodedata.normalize("NFC", text) != text or annotation["id"] in object_ids
                    or annotation["kind"] not in {"line", "word"}):
                raise ValueError(f"Invalid annotation in {ident}")
            object_ids.add(annotation["id"])
            if annotation["kind"] == "line":
                lines[annotation["id"]] = text
            else:
                words.setdefault(annotation["line_id"], []).append(text)
        if any(line not in lines or " ".join(items) != lines[line] for line, items in words.items()):
            raise ValueError(f"Logical word order does not reconstruct its line in {ident}")
        yield {**row, "image": str(path), "source_size": (width, height)}


def radial_remap(image, k1):
    height, width = image.shape[:2]
    y, x = np.mgrid[:height, :width].astype(np.float32)
    px, py = undistort(x + .5, y + .5, width, height, k1)
    return cv2.remap(image, (px - .5).astype(np.float32), (py - .5).astype(np.float32),
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def phone_jpeg(rgb, settings, seed, output, photometry=None):
    rgb = radial_remap(rgb, settings["k1"]).astype(np.float32) / 255
    noise = settings.get("noise_strength", 1)
    if photometry is not None:
        rgb = photometry.sharpen(photometry.apply_tone(rgb))
        noise *= photometry.sensor_noise_scale
    if noise:
        linear = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
        iso = settings["iso"] / 100
        shot, read = (.00022, .000003) if "noise_strength" in settings else (.000018, .0000008)
        sigma = noise * np.sqrt(shot * iso * linear + read * iso ** 2)
        linear = np.clip(linear + np.random.default_rng(seed ^ 54173).normal(0, sigma), 0, 1)
        rgb = np.where(linear <= .0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - .055)
    encoding = {"quality": settings["jpeg_quality"]}
    if photometry is not None:
        rgb = photometry.add_luma_noise(rgb, seed)
        if photometry.jpeg_tables:
            encoding = {"qtables": [list(table) for table in photometry.jpeg_tables]}
    Image.fromarray(np.rint(np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(
        output, subsampling=2, optimize=True, **encoding)


def fiducials(size, path, radius_fraction=.015):
    width, height = size
    img = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(img)
    radius = min(width, height) * radius_fraction
    for u, v in MARKERS:
        x, y = width * u - .5, height * v - .5
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 0, 255))
    img.save(path)


def marker_errors(image, expected, k1):
    pixels = radial_remap(image, k1)
    r, g, b = pixels.transpose((2, 0, 1)).astype(np.int16)
    mask = np.uint8((r > 150) & (b > 150) & (r - g > 95) & (b - g > 95))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    locations = [centers[i] + .5 for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= 3]
    if len(locations) != len(expected):
        raise ValueError(f"Found {len(locations)} of {len(expected)} raster fiducials")
    errors = []
    for point in expected:
        index = min(range(len(locations)), key=lambda i: np.linalg.norm(locations[i] - point))
        errors.append(float(np.linalg.norm(locations.pop(index) - point)))
    return errors


def open_rgb(path):
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def contextual_word_labels(annotations):
    """Bind word polygons to exact text through the parent line and logical index."""
    indices = {}
    for annotation in annotations:
        if annotation["kind"] == "word":
            parent = annotation["line_id"]
            index = indices.get(parent, 0)
            indices[parent] = index + 1
            yield {**{key: value for key, value in annotation.items() if key != "text"}, "word_index": index}
        else:
            yield annotation


def rejected_pairs(captures):
    """Keep an intact pair only after checking the same centred camera geometry."""
    if len(captures) % 2:
        raise ValueError("Paired captures must contain both arms")
    invalid = set()
    for i in range(0, len(captures), 2):
        clean, treated = captures[i:i + 2]
        if clean["pair_id"] != treated["pair_id"] or (clean["arm"], treated["arm"]) != ("clean", "treated"):
            raise ValueError("Misordered clean and treated twins")
        for field in ("scene", "paper", "clip_from_sheet", "annotations"):
            if clean[field] != treated[field]:
                raise ValueError(f"Twin geometry changed for {clean['pair_id']}: {field}")
        if clean["phone"]["k1"] != treated["phone"]["k1"]:
            raise ValueError(f"Twin radial coordinates changed for {clean['pair_id']}")
        if clean["rejected_regions"] or treated["rejected_regions"]:
            invalid.add(clean["pair_id"])
    return invalid


def make_duplex(source, destination):
    """A soft reflected absorption map for the faint reverse-side impression."""
    gray = cv2.cvtColor(open_rgb(source), cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    mirrored = np.uint8(np.clip((gray[:, ::-1].astype(np.float32) - 18) * (255 / 225), 0, 255))
    shifted = cv2.warpAffine(mirrored, np.float32([[1, 0, 0], [0, 1, height * .018]]), (width, height),
                            borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    Image.fromarray(cv2.GaussianBlur(shifted, (0, 0), 2.5)).save(destination)


def assign_strong_folds(cases, assignments, developable_paper, frozen_optics, *, rounded=False):
    if not developable_paper:
        raise ValueError("Explicit folds require developable paper")
    if not frozen_optics and (not rounded or any("realism" not in case for case in cases)):
        raise ValueError("Explicit folds require frozen optics or a seeded rounded-fold pair")
    ids = {row["pair_id"] for row in cases}
    profiles = {}
    options = ROUNDED_PROFILES if rounded else PROFILES
    field = "rounded_fold" if rounded else "strong_fold"
    for assignment in assignments:
        pair, sep, profile = assignment.partition("=")
        if not sep or pair not in ids or profile not in options or pair in profiles:
            raise ValueError(f"Expected a unique selected PAIR=PROFILE, got {assignment!r}")
        profiles[pair] = profile
    return [{**case, field: profiles[case["pair_id"]]} if case["pair_id"] in profiles else case for case in cases]


def frozen_cases(cases, path, inputs, assets, realism_seed, size, samples, required_pairs):
    """Recover exact v2 profiles, including individual optical settings of accepted retakes."""
    prior = json.loads(path.read_bytes())
    if (prior["schema"] != "heocr.capture3d.paired.v2" or prior["source_manifest_sha256"] != sha(inputs)
            or prior["realism_seed"] != realism_seed or prior["image_size"] != list(size)
            or prior["cycles_samples"] != samples or prior["scene_assets"] != assets):
        raise ValueError("Frozen v2 optics must match the source, scene assets and render settings")
    reference = {row["id"]: row for pair in prior["selected_pairs"] for row in pair}
    if required_pairs and set(required_pairs) - {row["pair_id"] for row in reference.values()}:
        raise ValueError("Requested pairs are outside the frozen v2 roster")
    for case in cases:
        original = reference.get(case["id"])
        if original is None:
            continue
        if case["sha256"] != original["source_sha256"] or any(
            case[key] != original[key] for key in ("seed", "font_sha256", "scene", "arm", "pair_id")
        ):
            raise ValueError(f"Frozen v2 source identity changed for {case['id']}")
        yield {**case, "realism": original["realism"], "frozen_phone": original["phone"]}


def run(inputs, assets, output, blender, device, size, samples, max_bad_fraction, realism_seed=None, pair_id=None,
        developable_paper=False, frozen_optics=None, strong_fold=None, rounded_fold=None, photometry_profile=None):
    if strong_fold and rounded_fold:
        raise ValueError("Choose one fold generation per batch")
    photometry = PhonePhotometry.read(photometry_profile) if photometry_profile else None
    if photometry and frozen_optics:
        raise ValueError("A new photometry profile cannot modify frozen optics")
    if photometry and photometry.blank_reverse and not developable_paper:
        raise ValueError("A blank reverse requires developable paper")
    input_manifest = json.loads(inputs.read_bytes())
    cases = list(source_rows(inputs))
    if not cases:
        raise ValueError("The source manifest contains no pages")
    paired = realism_seed is not None
    if developable_paper and not paired:
        raise ValueError("Developable paper uses the pinned paired capture recipes")
    if paired:
        cases = list(plan_realism(cases, realism_seed))
    if pair_id:
        if not paired or set(pair_id) - {row["pair_id"] for row in cases}:
            raise ValueError("Requested pairs must exist in the original paired roster")
        selected = set(pair_id)
        cases = [row for row in cases if row["pair_id"] in selected]
    asset_manifest = json.loads(assets.read_bytes())
    asset_pins = {key: {k: v for k, v in entry.items() if k != "path"} for key, entry in asset_manifest.items()}
    requested_assets = {}
    for role in ("desk", "floor", "environment"):
        entry = asset_manifest[role]
        if entry["licence"] != "CC0-1.0":
            raise ValueError(f"Expected a CC0 scene asset for {role}")
        requested_assets[role] = str(checked_file(assets.parent, entry["path"], entry["sha256"]))
    if frozen_optics:
        cases = list(frozen_cases(cases, frozen_optics, inputs, asset_pins, realism_seed, size, samples, pair_id))
        if not cases:
            raise ValueError("The frozen v2 roster has no matching input cases")
    if strong_fold or rounded_fold:
        cases = assign_strong_folds(cases, rounded_fold or strong_fold, developable_paper, frozen_optics,
                                   rounded=bool(rounded_fold))
    output.mkdir()
    (output / "assets").mkdir()
    scenetypes = set()
    with TemporaryDirectory(prefix=".blender-", dir=output.resolve().parent) as directory:
        temp = Path(directory)
        for case in cases:
            ident = case["id"]
            case["undistorted"] = str(temp / f"{ident}.png")
            if developable_paper and not (photometry and photometry.blank_reverse):
                reverse = temp / f"{case['pair_id']}-reverse.png"
                if case["arm"] == "clean":
                    make_duplex(case["image"], reverse)
                case["showthrough"] = str(reverse)
            if (paired and case["arm"] == "clean") or (not paired and case["scene"] not in scenetypes):
                scenetypes.add(case["scene"])
                case["marker_uv"] = MARKERS
                case["marker_image"] = str(temp / f"{ident}-uv.png")
                case["marker_output"] = str(temp / f"{ident}-markers.png")
                fiducials(case["source_size"], case["marker_image"], .0065 if developable_paper else .015)
        job, result_path = temp / "job.json", temp / "result.json"
        json_write(job, {"cases": cases, "result": str(result_path), "assets": requested_assets,
                         "device": device, "size": size, "samples": samples, "max_bad_fraction": max_bad_fraction,
                         "developable_paper": developable_paper})
        worker = Path(__file__).with_name("render.py")
        with (temp / "blender.log").open("wb") as log:
            result = subprocess.run([blender, "-b", "--factory-startup", "--python-exit-code", "1",
                                     "-P", str(worker), "--", str(job)], stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError((temp / "blender.log").read_text(errors="replace")[-7000:])
        run_result = json.loads(result_path.read_bytes())
        captures = run_result.pop("rows")
        invalid = rejected_pairs(captures) if paired else set()
        if developable_paper:
            for case, capture in zip(cases, captures, strict=True):
                positions = capture.pop("marker_positions")
                if positions and capture["pair_id"] not in invalid:
                    try:
                        errors = marker_errors(open_rgb(case["marker_output"]), positions, capture["phone"]["k1"])
                    except ValueError as exc:
                        capture["marker_failure"] = str(exc)
                        invalid.add(capture["pair_id"])
                        continue
                    capture["marker_check"] = {"count": len(errors), "mean_px": float(np.mean(errors)), "max_px": max(errors)}
                    if max(errors) >= 1:
                        capture["marker_failure"] = "Maximum raster fiducial error is at least one pixel"
                        invalid.add(capture["pair_id"])
        kept, rejected = [], []
        for case, capture in zip(cases, captures, strict=True):
            ident = capture["id"]
            if ident != case["id"]:
                raise ValueError("Blender changed the ordered capture identity")
            if "frozen_phone" in case and capture["phone"] != case["frozen_phone"]:
                raise ValueError(f"Blender changed the frozen v2 settings for {ident}")
            if capture["rejected_regions"] or capture.get("pair_id") in invalid:
                rejected.append({"id": ident, "scene": capture["scene"], "regions": capture["rejected_regions"],
                                 **({"marker_failure": capture["marker_failure"], "marker_check": capture.get("marker_check")}
                                    if "marker_failure" in capture else {})})
                continue
            photo = f"assets/{ident}-photo.jpg"
            raw = f"assets/{ident}-raw.png"
            shutil.copyfile(case["image"], output / raw)
            phone_jpeg(open_rgb(case["undistorted"]), capture["phone"], case["seed"], output / photo, photometry)
            capture["annotations"] = list(contextual_word_labels(capture["annotations"]))
            capture.update(seed=case["seed"], font_sha256=case["font_sha256"], image=photo,
                           image_sha256=sha(output / photo), source_image=raw, source_sha256=case["sha256"])
            positions = capture.pop("marker_positions", [])
            if positions:
                errors = marker_errors(open_rgb(case["marker_output"]), positions, capture["phone"]["k1"])
                capture["marker_check"] = {"count": len(errors), "mean_px": float(np.mean(errors)), "max_px": max(errors)}
                if max(errors) > 2:
                    raise ValueError(f"Marker reprojection exceeded 2 px for {ident}")
            kept.append(capture)
    if not kept:
        raise ValueError("Every render failed the frame or visibility threshold")
    run_result["camera_renders_per_minute"] = 60 * len(kept) / sum(row["render_seconds"] for row in kept)
    run_result["pilot_renders_per_minute"] = 60 * len(kept) / run_result["elapsed_seconds"]
    version = "paired.v2" if paired else "v1"
    if developable_paper:
        version = "paired.v4" if strong_fold else "paired.v3"
        if rounded_fold:
            version = "paired.v5"
    json_write(output / "generation_manifest.json", {
        "schema": f"heocr.capture3d.{version}",
        **({"realism_seed": realism_seed} if paired else {}), "split": "train-calibration", "licence": "CC0-1.0",
        "text_gate_sha256": input_manifest["text_gate_sha256"], "fonts_guard_sha256": input_manifest["fonts_guard_sha256"],
        "source_manifest_sha256": sha(inputs), "scene_assets": asset_pins,
        **({"frozen_v2_optics_sha256": sha(frozen_optics)} if frozen_optics else {}),
        **({"photometry_profile_sha256": sha(photometry_profile)} if photometry else {}),
        "camera": run_result, "image_size": size, "cycles_samples": samples, "device": device,
        "coordinate_space": "pixel edges from top left; mesh projection at shutter centre after lens distortion",
        "max_bad_sample_fraction": max_bad_fraction, "renders": kept, "rejected": rejected})
    print(f"{len(kept)} rendered, {len(rejected)} rejected, {run_result['pilot_renders_per_minute']:.2f} renders/min incl. GT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "assets", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--device", choices=("METAL", "CPU"), default="METAL")
    parser.add_argument("--size", nargs=2, type=int, default=(720, 960), metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--realism-seed", type=int, help="Generate same-scene clean and treated twins")
    parser.add_argument("--developable-paper", action="store_true", help="Use matte, developable v3 paper with the same v2 optics")
    parser.add_argument("--frozen-optics", type=Path, help="Hold each optical setting to an exact v2 gallery manifest")
    parser.add_argument("--pair-id", action="append", help="Retake a pair without changing its original scene recipe")
    parser.add_argument("--strong-fold", action="append", metavar="PAIR=PROFILE",
                        help=f"Apply a developable fold to both arms. Profiles: {', '.join(PROFILES)}")
    parser.add_argument("--rounded-fold", action="append", metavar="PAIR=PROFILE",
                        help=f"Apply rounded creases to both arms. Profiles: {', '.join(ROUNDED_PROFILES)}")
    parser.add_argument("--photometry-profile", type=Path, help="Opt-in phone tone, noise, JPEG and reverse-side JSON")
    parser.add_argument("--max-bad-fraction", type=float, default=0)
    args = parser.parse_args()
    if min(args.size) < 160 or max(args.size) > 4096 or args.samples < 4 or not 0 <= args.max_bad_fraction <= .10:
        parser.error("Expected canvas dimensions in [160, 4096], samples >= 4 and bad fraction in [0, .10]")
    run(**vars(args))


if __name__ == "__main__":
    main()
