"""Fit or check scanifier profiles from explicit, non-test development captures."""
import argparse
import hashlib
import io
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps, JpegImagePlugin

from .dev_profiles import _noise, _render, RANGE_BOUNDS, sample_profile, validate_profile


FIT_NAMES = ("phone_flat", "phone_oblique", "adobe_scan")
PATCH = 32
AXIS = (np.arange(PATCH) + 0.5 - PATCH / 2) / PATCH
PLANES = np.column_stack((np.ones(PATCH ** 2), np.tile(AXIS, PATCH), np.repeat(AXIS, PATCH)))
PLANE_FIT = np.linalg.pinv(PLANES)
WINDOW = np.outer(np.hanning(PATCH), np.hanning(PATCH))
FREQ = np.hypot(np.fft.fftfreq(PATCH)[:, None], np.fft.rfftfreq(PATCH)[None, :])
FFT_WEIGHT = np.r_[1, np.full(PATCH // 2 - 1, 2), 1]
BAND = (FREQ > 0) & (FREQ <= 0.18)


def _page_mask(gray):
    """Find the largest contiguous light sheet at low resolution."""
    height, width = gray.shape
    scale = min(1, 320 / max(width, height))
    small = cv2.resize(gray, (max(1, round(width * scale)), max(1, round(height * scale))),
                       interpolation=cv2.INTER_AREA)
    cutoff, _ = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    mask = (small > min(cutoff, np.quantile(small, 0.40)) - 1).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    canvas = np.zeros_like(small)
    if contours:
        cv2.drawContours(canvas, [max(contours, key=cv2.contourArea)], -1, 1, cv2.FILLED)
    box = cv2.boundingRect(canvas)
    inner = cv2.erode(canvas, np.ones((11, 11), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return cv2.resize(inner, (width, height), interpolation=cv2.INTER_NEAREST).astype(bool), box


def _residual(patches):
    flat = patches.reshape(-1, PATCH ** 2)
    return (flat - (flat @ PLANE_FIT.T) @ PLANES.T).reshape(-1, PATCH, PATCH)


def _spectrum(residual):
    power = np.abs(np.fft.rfft2(residual * WINDOW)) ** 2 * FFT_WEIGHT
    all_power = power.sum(axis=(-2, -1))
    return power[:, BAND].sum(axis=1) / np.maximum(all_power, 1e-12)


def _paper_and_noise(rgb, gray, mask, box):
    height, width = gray.shape
    x0, y0, bw, bh = box
    scale = min(1, 320 / max(width, height))
    xgrid = np.linspace(PATCH // 2, width - PATCH // 2, 28).astype(int)
    ygrid = np.linspace(PATCH // 2, height - PATCH // 2, 28).astype(int)
    coords = [(x, y) for y in ygrid for x in xgrid if mask[y, x]]
    tiles = [(slice(y - 16, y + 16), slice(x - 16, x + 16)) for x, y in coords]
    if len(tiles) < 16:
        return {}
    patches = np.array([gray[t] for t in tiles], dtype=np.float32)
    residual = _residual(patches)
    tile_level = np.median(patches, axis=(1, 2))
    spread = np.ptp(np.quantile(residual, [0.02, 0.98], axis=(1, 2)), axis=0)
    # Reject text, then prefer the flatter tiles within this capture. The tile
    # median cutoff is relative to the page to retain underlit areas.
    good = (spread <= min(18, np.quantile(spread, 0.42))) & (tile_level > np.quantile(tile_level, 0.10) - 1)
    if good.sum() < 16:
        return {}
    rgb_med = np.asarray([np.median(rgb[t], axis=(0, 1)) for t, keep in zip(tiles, good) if keep])
    xy = np.asarray(coords)[good] * scale
    normalized = (xy - [x0, y0]) / [bw, bh] - 0.5
    design = np.column_stack((np.ones(len(xy)), normalized))
    paper = np.log(np.maximum(rgb_med, 1))
    fit, *_ = np.linalg.lstsq(design, paper, rcond=None)
    for _ in range(3):
        errors = np.max(np.abs(paper - design @ fit), axis=1)
        keep = errors <= np.quantile(errors, 0.80)
        fit, *_ = np.linalg.lstsq(design[keep], paper[keep], rcond=None)
    kept_residual = residual[good]
    sd = kept_residual.std(axis=(1, 2))
    usable = sd > 0.05
    spectrum = _spectrum(kept_residual[usable])
    result = dict(zip(("paper_r", "paper_g", "paper_b"), np.exp(fit[0]).clip(0, 255).tolist()))
    result.update(gradient_x=float(fit[1].mean()), gradient_y=float(fit[2].mean()),
                  noise_sd=float(np.median(sd)), noise_tiles=int(good.sum()))
    if usable.sum() >= 12 and np.median(sd) > 0.05:
        lower, upper = np.quantile(sd, [0.16, 0.84])
        result.update(noise_band=float(np.median(spectrum)),
                      noise_cv=float((upper - lower) / (2 * np.median(sd))))
    return result


def _edge_samples(gray, mask, box, rng):
    """Screen straight printed transitions and estimate Gaussian-equivalent SFR."""
    height, width = gray.shape
    scale = min(1, 320 / max(width, height))
    x0, y0, bw, bh = box
    samples = []
    for axis in (0, 1):
        plane = gray if axis == 0 else gray.T
        roi = mask if axis == 0 else mask.T
        # Pick candidate steps on three neighboring scan lines. Rank by step
        # size to favor isolated ink–paper transitions rather than texture.
        low = plane[1:-1, 8:-8].astype(np.int16)
        jump = np.abs(plane[1:-1, 9:-7].astype(np.int16) - low)
        eligible = np.flatnonzero((jump >= 38) & roi[1:-1, 8:-8])
        if len(eligible) > 6000:
            eligible = rng.choice(eligible, 6000, replace=False)
        row, col = np.unravel_index(eligible, jump.shape)
        row, col = row + 1, col + 8
        across = col[:, None, None] + np.arange(-4, 6)[None, None, :]
        along = row[:, None, None] + np.arange(-1, 2)[None, :, None]
        local = plane[along, across].astype(np.float32)
        # Align only transitions with consistent contrast and direction.
        profiles = local.mean(axis=1)
        start, end = profiles[:, :2].mean(axis=1), profiles[:, -2:].mean(axis=1)
        delta = end - start
        safe_delta = np.where(delta == 0, 1, delta)
        normalized = (profiles - start[:, None]) / safe_delta[:, None]
        steps = np.diff(normalized, axis=1)
        valid = (np.abs(delta) >= 85) & (steps.min(axis=1) >= -0.08)
        valid &= (np.abs(local[:, 0] - local[:, -1]).mean(axis=1) < np.abs(delta) * 0.16)
        for index in np.flatnonzero(valid):
            trace = np.maximum.accumulate(normalized[index])
            if trace[0] > 0.10 or trace[-1] < 0.90:
                continue
            p10, p90 = np.interp([0.10, 0.90], trace, np.arange(len(trace)))
            sigma = (p90 - p10) / 2.5631
            x, y = (col[index], row[index]) if axis == 0 else (row[index], col[index])
            radius = np.hypot((x * scale - x0) / bw - 0.5, (y * scale - y0) / bh - 0.5)
            # MTF50 proxy from the line-spread function at native sampling.
            response = np.abs(np.fft.rfft(np.diff(trace), n=128))
            response /= max(response[0], 1e-6)
            below = np.flatnonzero(response < 0.5)
            if below.size:
                j = below[0]
                mtf50 = np.interp(0.5, response[j-1:j+1][::-1], [j / 128, (j - 1) / 128])
            else:
                mtf50 = 0.5  # right-censored at Nyquist
            samples.append((axis, radius, float(sigma), float(mtf50)))
    return np.asarray(samples).reshape(-1, 4)


def _measure(image, seed):
    # Decode source JPEG metadata before orientation conversion, and compare
    # edges/noise on native, unrectified pixels.
    tables = getattr(image, "quantization", None)
    mode = JpegImagePlugin.get_sampling(image) if tables else -1
    rgb = np.asarray(ImageOps.exif_transpose(image).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mask, box = _page_mask(gray)
    result = _paper_and_noise(rgb, gray, mask, box)
    edges = _edge_samples(gray, mask, box, np.random.default_rng(seed))
    result["edge_count"] = len(edges)
    if len(edges) >= 20:
        sigma = float(np.median(edges[:, 2]))
        result.update(edge_sigma=sigma, mtf50_proxy=float(np.median(edges[:, 3])))
        for axis in (0, 1):
            widths = edges[edges[:, 0] == axis, 2]
            if len(widths) >= 10:
                result[f"edge_sigma_{axis}"] = float(np.median(widths))
        for name, selected in (("center", edges[:, 1] <= 0.23), ("outer", edges[:, 1] >= 0.36)):
            if np.count_nonzero(selected) >= 10:
                result[f"edge_sigma_{name}"] = float(np.median(edges[selected, 2]))
    if tables:
        qtables = [table for _, table in sorted(tables.items())]
        result["jpeg_luma_step"] = float(np.median(qtables[0]))
        result["jpeg_luma_dc"] = qtables[0][0]
        if mode >= 0:
            result["jpeg_encoder"] = {"subsampling": mode, "qtables": qtables}
    return result


def _manifest(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("purpose") != "non_test_development_calibration":
        raise ValueError("Manifest must explicitly designate non-test development calibration")
    entries = {"fit": [], "check": []}
    split_by_page = {}
    seen = set()
    images = set()
    for record in doc["captures"]:
        # The manifest is an explicit allowlist, never a recursive input scan.
        file = Path(record["file"]).resolve(strict=True)
        group, profile, page = record["split"], record["profile"], record["page"]
        forbidden = {"eval_refs", "ps_v1", "nq1", "preregistration", "heocr-restricted-eval"}
        if forbidden.intersection(part.lower() for part in file.parts) or any(
            part.lower() == "runs" and i + 1 < len(file.parts) and "test" in file.parts[i + 1].lower()
            for i, part in enumerate(file.parts)
        ):
            raise ValueError("Evaluation paths are forbidden")
        if (group not in entries or profile not in FIT_NAMES or file in images
                or (profile, page) in seen or split_by_page.setdefault(page, group) != group):
            raise ValueError("Each physical page must stay in one split with unique images and views")
        seen.add((profile, page))
        images.add(file)
        entries[group].append((profile, page, file))
    return entries


def _measures(records, seed):
    groups = {name: [] for name in FIT_NAMES}
    for profile, page, path in records:
        with Image.open(path) as image:
            values = _measure(image, seed)
        with path.open("rb") as file:
            checksum = hashlib.file_digest(file, "sha256").hexdigest()
        groups[profile].append({"page": page, "sha256": checksum, "metrics": values})
    return groups


def _band_to_mix():
    values = np.linspace(0, 1, 41)
    data = []
    for mix in values:
        noise = _noise((PATCH * 8, PATCH * 8),
                       {"noise_low_mix": mix, "noise_cv": 0, "noise_sd": 1}, np.random.default_rng(4))
        tiles = noise.reshape(8, PATCH, 8, PATCH).transpose(0, 2, 1, 3).reshape(-1, PATCH, PATCH)
        data.append(np.median(_spectrum(_residual(tiles))))
    return np.maximum.accumulate(data), values


def _fit_profile(name, records, seed, transfer):
    if len(records) < 3:
        raise ValueError(f"{name} needs at least three fit pages")
    samples = [dict(record["metrics"]) for record in records]
    for sample in samples:
        if "noise_band" in sample:
            sample["noise_low_mix"] = float(np.interp(sample["noise_band"], *transfer))
        # Pixel aperture and the linear interpolation in the edge estimator
        # impart a nonzero width even to a perfectly sharp rendered edge.
        if "edge_sigma" in sample:
            widest = max(sample.get("edge_sigma_0", sample["edge_sigma"]),
                         sample.get("edge_sigma_1", sample["edge_sigma"]))
            narrowest = min(sample.get("edge_sigma_0", sample["edge_sigma"]),
                            sample.get("edge_sigma_1", sample["edge_sigma"]))
            sample["blur_sigma"] = float(np.sqrt(max(0, narrowest ** 2 - (0.8 / 2.5631) ** 2)))
            if "edge_sigma_outer" in sample and "edge_sigma_center" in sample:
                sample["defocus_add"] = max(0, sample["edge_sigma_outer"] - sample["edge_sigma_center"])
            sample["motion_px"] = float(np.sqrt(12 * max(0, widest ** 2 - narrowest ** 2)))
            sample["motion_deg"] = 0 if sample.get("edge_sigma_0", 0) >= sample.get("edge_sigma_1", 0) else 90
    defaults = {"paper_r": 255, "paper_g": 255, "paper_b": 255}
    ranges, coverage = {}, {}
    for key, (lower, upper) in RANGE_BOUNDS.items():
        available = [sample[key] for sample in samples if key in sample]
        coverage[key] = len(available)
        if len(available) < 3:
            if key in ("paper_r", "paper_g", "paper_b", "gradient_x", "gradient_y", "noise_sd", "blur_sigma"):
                raise ValueError(f"{name} has insufficient fit observations for {key}")
            ranges[key] = [defaults.get(key, 0)] * 2
            continue
        band = np.clip(np.quantile(available, [0.10, 0.90]), lower, upper)
        ranges[key] = np.round(band, 5).tolist()
    # Axis-aligned proxy only. Retain the median axis rather than generating
    # intermediate angles from two discrete direction observations.
    angles = [sample["motion_deg"] for sample in samples if "motion_deg" in sample]
    if angles:
        ranges["motion_deg"] = [sorted(angles)[(len(angles) - 1) // 2]] * 2
    encoders = [sample["jpeg_encoder"] for sample in samples if "jpeg_encoder" in sample]
    if encoders and len(encoders) != len(samples):
        raise ValueError(f"{name} must use one consistent endpoint format")
    profile = {"version": 1, "name": name, "status": "dev_fit", "seed": seed, "ranges": ranges,
               "jpeg_encoders": encoders}
    validate_profile(profile)
    return profile, coverage


def _old_flatbed(seed):
    defaults = {"paper_r": [223, 251], "paper_g": [216, 247], "paper_b": [192, 238],
                "gradient_x": [-0.10, 0.10], "gradient_y": [-0.10, 0.10],
                "blur_sigma": [0.25, 1.25], "noise_sd": [0.3, 2.0],
                "noise_low_mix": [0.1, 0.5], "noise_cv": [0.1, 0.4],
                "show_through_opacity": [0.02, 0.12], "scanner_edge_fraction": [0.005, 0.04],
                "scanner_bar_fraction": [0.002, 0.015], "scanner_bars": [0, 2]}
    return {"version": 1, "name": "flatbed_old", "status": "prior_only", "seed": seed,
            "ranges": {key: defaults.get(key, [0, 0]) for key in RANGE_BOUNDS}, "jpeg_encoders": []}


def _probe():
    """Project-authored raster of blank paper and distributed printed edges."""
    result = Image.new("RGB", (768, 1024), "white")
    draw = ImageDraw.Draw(result)
    for y in range(60, 980, 64):
        for x in range(45, 715, 32):
            draw.rectangle((x, y, x + 12, y + 11), fill=(26, 26, 26))
    return result



def _measure_rendered(rendered, seed):
    if isinstance(rendered, bytes):
        with Image.open(io.BytesIO(rendered)) as image:
            return _measure(image, seed)
    return _measure(rendered, seed)


def _forward_fit(profile, records):
    """Correct estimator and JPEG biases using only fit captures and a fixed probe."""
    stimulus = _probe()
    targets = {
        "noise_sd": 0.15, "noise_band": 0.05, "noise_cv": 0.08,
        "edge_sigma": 0.12, "mtf50_proxy": 0.04,
        "edge_sigma_center": 0.18, "edge_sigma_outer": 0.18,
    }
    weights = {}
    for key, floor in targets.items():
        values = [r["metrics"][key] for r in records if key in r["metrics"]]
        if len(values) >= 3:
            lo, med, hi = np.quantile(values, [0.25, 0.5, 0.75])
            weights[key] = (float(med), max(float(hi - lo), floor))

    seed = profile["seed"] + 1000
    params = sample_profile(profile, seed)
    # Use the middle of each fitted range for the response correction. Leave
    # the inter-page spread intact except where it reaches physical bounds.
    params.update({key: float(np.mean(value)) for key, value in profile["ranges"].items()
                   if key != "scanner_bars"})

    def objective(candidate):
        measured = _measure_rendered(_render(stimulus, candidate, seed, None), seed)
        return sum(abs(measured[key] - median) / scale if key in measured else 8
                   for key, (median, scale) in weights.items())

    start = objective(params)
    best = start
    changes = {}
    steps = {"noise_sd": 0.35, "noise_low_mix": 0.10, "noise_cv": 0.10,
             "blur_sigma": 0.16, "defocus_add": 0.19, "motion_px": 0.27}
    for factor in (1, 0.5):
        for key, step in steps.items():
            original = params[key]
            if profile["name"] == "adobe_scan" and key.startswith("noise_") and original == 0:
                continue  # clipped white regions cannot identify latent noise
            low, high = RANGE_BOUNDS[key]
            for shift in (-2, -1, 1, 2):
                value = float(np.clip(original + factor * step * shift, low, high))
                if value == original:
                    continue
                score = objective(params | {key: value})
                if score < best - 1e-6:
                    best = score
                    params[key] = value
            changes[key] = changes.get(key, 0) + params[key] - original
    for key, shift in changes.items():
        profile["ranges"][key] = np.round(np.clip(np.asarray(profile["ranges"][key]) + shift,
                                                   *RANGE_BOUNDS[key]), 5).tolist()
    validate_profile(profile)
    return {"start_loss": start, "end_loss": best, "probe_seed": seed, "adjustments": changes}

def _distances(fit, check):
    """KS D and empirical Wasserstein-1, with no significance claim."""
    a, b = np.sort(fit), np.sort(check)
    knots = np.unique(np.r_[a, b])
    delta = np.abs(np.searchsorted(a, knots, side="right") / len(a)
                   - np.searchsorted(b, knots, side="right") / len(b))
    return {"n_reference": len(a), "n_check": len(b), "ks_d": float(np.max(delta)),
            "wasserstein_1": float(np.dot(np.diff(knots), delta[:-1]))}


def _check_profile(profile, records, seed):
    stimulus = _probe()
    predictions = []
    seeds = []
    for index in range(12):
        render_seed = seed + index
        seeds.append(render_seed)
        rendered = _render(stimulus, sample_profile(profile, render_seed), render_seed, None)
        predictions.append(_measure_rendered(rendered, seed))
    observed_jpeg = [r["metrics"]["jpeg_encoder"] for r in records if "jpeg_encoder" in r["metrics"]]
    return {"seeds": seeds, "probe": predictions, "comparisons": _compare(predictions, records),
            "jpeg_table_matches": {
                "n": len(observed_jpeg),
                "exact": sum(encoder in profile["jpeg_encoders"] for encoder in observed_jpeg),
            }}



def _compare(predictions, records):
    # Quantize numerical precision before computing empirical CDFs. An
    # exactly white region can differ in floating-point least-squares noise.
    decimals = {
        "paper_r": 2, "paper_g": 2, "paper_b": 2,
        "gradient_x": 4, "gradient_y": 4,
        "noise_sd": 3, "noise_cv": 4, "noise_band": 4,
        "edge_sigma": 3, "edge_sigma_center": 3, "edge_sigma_outer": 3,
        "mtf50_proxy": 4, "jpeg_luma_dc": 0, "jpeg_luma_step": 1,
    }
    checks = {}
    for field, places in decimals.items():
        a = [round(row[field], places) for row in predictions if field in row]
        b = [round(row["metrics"][field], places) for row in records if field in row["metrics"]]
        if a and b:
            checks[field] = _distances(a, b)
    return checks

def _write(path, value):
    with path.open("x", encoding="utf-8") as file:
        file.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("fit", "check"))
    parser.add_argument("manifest", type=Path, help="Explicit allowlist for non-test dev calibration")
    parser.add_argument("profiles", type=Path, help="New profile directory for fit, existing for check")
    parser.add_argument("report", type=Path, help="New private JSON report path")
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be nonnegative")
    cv2.setNumThreads(1)
    manifest = _manifest(args.manifest)
    if args.action == "fit":
        samples = _measures(manifest["fit"], args.seed)
        transfer = _band_to_mix()
        profiles, coverage, forward_fit = {}, {}, {}
        for index, name in enumerate(FIT_NAMES):
            profiles[name], coverage[name] = _fit_profile(name, samples[name], args.seed + index, transfer)
            forward_fit[name] = _forward_fit(profiles[name], samples[name])
        profiles["flatbed_old"] = _old_flatbed(args.seed + len(FIT_NAMES))
        args.profiles.mkdir()
        for name, profile in profiles.items():
            _write(args.profiles / f"{name}.json", profile)
        _write(args.report, {"seed": args.seed, "fit": samples, "coverage": coverage, "forward_fit": forward_fit})
    else:
        from .dev_profiles import read_profile

        profiles = {name: read_profile(args.profiles / f"{name}.json") for name in FIT_NAMES}
        if any(len([r for r in manifest["check"] if r[0] == name]) < 2 for name in FIT_NAMES):
            raise ValueError("Each compared profile requires at least two reserved physical pages")
        samples = _measures(manifest["check"], args.seed)
        _write(args.report, {"seed": args.seed, "dev_check": samples, "comparisons": {
            name: _check_profile(profiles[name], samples[name], args.seed + 100 * index)
            for index, name in enumerate(FIT_NAMES)}})


if __name__ == "__main__":
    main()
