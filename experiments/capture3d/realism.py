# SPDX-License-Identifier: CC0-1.0
"""Deterministic scene recipes for controlled phone-artifact comparisons."""

from copy import deepcopy
import random


# Reflectance multipliers in scene-linear RGB, with calibrated surface roughness.
PAPER = {
    "white": ((1.0, 1.0, 1.0), .31),
    "off-white": ((.93, .91, .84), .49),
    "cream": ((.91, .80, .61), .52),
    "aged yellow": ((.83, .64, .36), .59),
    "recycled grey": ((.68, .70, .68), .68),
    "pale blue stock": ((.64, .79, .95), .38),
}


def lamp(name, kind, position, power, size, color, *, target=(0, 0, .01), cone=0):
    return dict(name=name, kind=kind, location=position, target=target, power=power,
                size=size, color=color, spot_degrees=cone)


LIGHT = {
    "daylight window": (.27, (1, 1, 1), [lamp("Window", "AREA", (-.29, .27, .44), 12, .43, (.88, .96, 1))]),
    "hard warm desk lamp": (.13, (1, .82, .68), [lamp("Tungsten desk spot", "SPOT", (-.22, .08, .46), 9, .025,
                                                      (1, .67, .33), target=(.03, -.01, .01), cone=59)]),
    "cool LED": (.18, (.66, .78, 1), [lamp("LED panel", "AREA", (.24, .13, .31), 10, .16, (.68, .83, 1))]),
    "raking side light": (.14, (.92, .98, 1), [lamp("Low side lamp", "AREA", (-.40, -.078, .16), 16, .115,
                                                    (1, .95, .79))]),
    "coloured ambient": (.29, (.69, .83, 1), [lamp("Warm bouncing light", "AREA", (.19, -.26, .28), 7, .27,
                                                     (1, .64, .41))]),
    "mixed warm and cool": (.14, (.86, .91, 1), [lamp("Warm key", "SPOT", (-.30, -.13, .39), 7.5, .036,
                                                         (1, .65, .34), cone=63),
                                                  lamp("Cool fill", "AREA", (.27, .27, .36), 6.5, .22, (.54, .75, 1))]),
}

FOLDS = ("light curl", "deep crease", "double fold", "crumple", "dog-ear", "crumple and dog-ear")
EFFECTS = ((), ("noise",), ("flash",), ("motion",), ("defocus",), ("noise", "motion"),
           ("noise", "flash", "defocus"), ("flash", "motion"), ("motion", "defocus"),
           ("noise", "defocus"), ("noise", "flash"), ())


def sample_folds(profile, rng):
    mesh = {"divisions": (64, 88)}
    if profile in {"deep crease", "double fold", "crumple"}:
        mesh.update(valley_depth=rng.uniform(.024, .037), valley_v=rng.uniform(.45, .70),
                    valley_angle=rng.uniform(-.20, .24))
    if profile == "double fold":
        mesh.update(crease_height=rng.uniform(.027, .042), crease_u=rng.uniform(.33, .69),
                    crease_width=rng.uniform(.028, .045), crease_angle=rng.uniform(-.22, .22))
    if "crumple" in profile:
        mesh.update(crumple=rng.uniform(.012, .022), curl=rng.uniform(.009, .018))
    if "dog-ear" in profile:
        mesh.update(dogear_size=rng.uniform(.034, .054), dogear_angle_deg=rng.uniform(34, 66),
                    dogear_corner=(rng.choice((-1, 1)), rng.choice((-1, 1))))
    return mesh


def plan_realism(cases, seed):
    """Uniformly cycle each profile before repeating, with independent permutations."""
    rng = random.Random(seed)
    decks = [list(deck) for deck in (PAPER, LIGHT, FOLDS, EFFECTS)]
    for deck in decks:
        rng.shuffle(deck)
    for index, case in enumerate(cases):
        for deck in decks:
            if index and index % len(deck) == 0:
                rng.shuffle(deck)
        stock, lighting, fold, effects = (deck[index % len(deck)] for deck in decks)
        case_rng = random.Random(case["seed"] ^ seed)
        reflectance, roughness = PAPER[stock]
        strength, tint, lamps = LIGHT[lighting]
        paper = {"stock": stock, "reflectance_rgb": reflectance, "roughness": roughness}
        scene_light = {"profile": lighting, "ambient_strength": strength, "ambient_rgb": tint, "sources": lamps}
        geometry = {"profile": fold, "settings": sample_folds(fold, case_rng)}
        iso = case_rng.randint(480, 1420) if "noise" in effects else 100
        camera = {"noise_strength": case_rng.uniform(.82, 1.36) if "noise" in effects else 0,
                  "iso": iso, "flash_w": case_rng.uniform(3.2, 6.8) if "flash" in effects else 0,
                  "flash_x_m": case_rng.choice((-.023, .023)),
                  "flash_uv": (case_rng.choice((.24, .72)), case_rng.choice((.20, .76))),
                  "flash_cone_deg": case_rng.uniform(24, 34),
                  "motion_m": case_rng.uniform(.0011, .0028) if "motion" in effects else 0,
                  "motion_angle_deg": case_rng.uniform(-62, 61),
                  "focus_offset_m": case_rng.choice((-1, 1)) * case_rng.uniform(.016, .038) if "defocus" in effects else 0,
                  "fstop": case_rng.uniform(2.05, 3.45) if "defocus" in effects else None}
        settings = {"paper": paper, "lighting": scene_light, "fold": geometry}
        for arm in ("clean", "treated"):
            profile = deepcopy(settings)
            profile["camera"] = dict(camera)
            if arm == "clean":
                profile["camera"].update(noise_strength=0, iso=100, flash_w=0, motion_m=0, focus_offset_m=0, fstop=None)
            yield {**case, "id": f"{case['id']}-{arm}", "pair_id": case["id"], "arm": arm, "realism": profile}
