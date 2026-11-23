"""Fit observed phone geometry and in-page optics from approved TRAIN pairs."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
from PIL import Image

from .dev_profiles import LIGHTING_KEYS, RANGE_BOUNDS, validate_profile
from .fit_dev_profiles import _band_to_mix, _fit_profile, _measure
from .fit_phone_training import load_rgb, observe, read_pairs
from .phone_training import phone_warp

ENDPOINTS = ("phone_flat", "phone_oblique")
SEED = 47261


def fit_train(manifest):
    """Fit the TRAIN allowlist. QA images are loaded by a separate caller."""
    cv2.setNumThreads(1)
    geometry = {name: [] for name in ENDPOINTS}
    optics = {name: [] for name in ENDPOINTS}
    rejected = []
    counts = {name: 0 for name in ENDPOINTS}
    transfer = _band_to_mix()
    for i, row in enumerate(read_pairs(manifest, train_only=True)):
        mode, page = row["profile"], row["page_id"]
        counts[mode] += 1
        cv2.setRNGSeed(SEED + i)
        capture = load_rgb(row["capture_path"])
        source = load_rgb(row["source_path"])
        try:
            variation = observe(source, capture, preserve_frame=True)
            phone_warp(
                source.size,
                size=capture.size,
                quad=variation["quad"],
                curl=variation["curl"],
                preserve_frame=True,
            )
        except ValueError as error:
            rejected.append(
                {
                    "capture_sha256": row["capture_sha256"],
                    "phase": "geometry",
                    "reason": str(error),
                }
            )
            continue
        keys = {key: row[key] for key in ("page_id", "source_sha256", "capture_sha256")}
        geometry[mode].append(keys | variation)
        if not row["optics_eligible"]:
            rejected.append(
                {
                    "capture_sha256": row["capture_sha256"],
                    "phase": "optics",
                    "reason": "foreground review hold",
                }
            )
            continue
        with Image.open(row["capture_path"]) as jpg:
            try:
                metrics = _measure(jpg, SEED + i, page_quad=variation["quad"])
            except ValueError as error:
                rejected.append(
                    {
                        "capture_sha256": row["capture_sha256"],
                        "phase": "optics",
                        "reason": str(error),
                    }
                )
                continue
        optics[mode].append(
            {"page": page, "sha256": row["capture_sha256"], "metrics": metrics}
        )

    profiles, coverage, unsupported = {}, {}, {}
    for mode in ENDPOINTS:
        geometry_pages = {row["page_id"] for row in geometry[mode]}
        optical_pages = {row["page"] for row in optics[mode]}
        report = {
            "input_captures": counts[mode],
            "geometry_captures": len(geometry[mode]),
            "geometry_pages": len(geometry_pages),
            "optical_captures": len(optics[mode]),
            "optical_pages": len(optical_pages),
        }
        coverage[mode] = report
        if min(len(geometry_pages), len(optical_pages)) < 3:
            unsupported[mode] = (
                "Fewer than three distinct source pages for geometry or optics"
            )
            continue
        # Require three actual pages for each fitted quantity, including cases
        # where several photos of one physical page provide the same statistic.
        metric_pages = {}
        for row in optics[mode]:
            for key in row["metrics"]:
                metric_pages.setdefault(key, set()).add(row["page"])
        for row in optics[mode]:
            row["metrics"] = {
                k: v for k, v in row["metrics"].items() if len(metric_pages[k]) >= 3
            }
        report["parameter_pages"] = {k: len(pages) for k, pages in metric_pages.items()}
        lighting = [
            row for row in optics[mode] if set(LIGHTING_KEYS) <= row["metrics"].keys()
        ]
        if len({row["page"] for row in lighting}) < 3:
            unsupported[mode] = (
                "Fewer than three source pages with joint lighting observations"
            )
            continue
        try:
            profile, _ = _fit_profile(mode, optics[mode], SEED, transfer)
        except ValueError as error:
            unsupported[mode] = str(error)
            continue
        profile["status"] = "train_fit"
        profile["lighting_samples"] = [
            {
                key: round(min(upper, max(lower, row["metrics"][key])), 5)
                for key, (lower, upper) in (
                    (key, RANGE_BOUNDS[key]) for key in LIGHTING_KEYS
                )
            }
            for row in lighting
        ]
        validate_profile(profile)
        profiles[mode] = profile

    bank = {
        "schema": "scanifier_phone_bank.v1",
        "fit_split": "train",
        "framing": "observed",
        "profiles": {key: geometry[key] for key in profiles},
    }
    evidence = {
        "fit_split": "train",
        "input_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
        "coverage": coverage,
        "rejected_measurements": rejected,
        "unsupported_endpoints": unsupported,
    }
    return bank, profiles, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    bank, profiles, evidence = fit_train(args.manifest)
    args.out.mkdir()
    for filename, value in (
        ("phone-bank.json", bank),
        ("fit-evidence.json", evidence),
        *((f"{name}.json", profile) for name, profile in profiles.items()),
    ):
        (args.out / filename).write_text(
            json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
        )
    if not profiles:
        raise SystemExit("Neither phone endpoint had enough TRAIN support")


if __name__ == "__main__":
    main()
