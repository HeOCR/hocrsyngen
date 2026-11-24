"""Build the CC0 Realism v2 visual preview with no external image inputs."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

from experiments.scanifier_v2.degradations import show_through, soft_scanner_edge, spatial_noise
from experiments.scanifier_v2.dev_profiles import apply_profile, read_profile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FONTS = ROOT / "src/hocrsyngen/data/synthetic/fonts"
PRESETS = HERE.parent / "presets"
W, H = 960, 1240
CONTROL_FONT = "NotoSansHebrew-wdth-wght.ttf"
FONT_PAIRS = (
    ("DavidLibre-Regular.ttf", "FrankRuhlLibre-wght.ttf"),
    ("Rubik-wght.ttf", "Assistant-wght.ttf"),
    ("MiriamLibre-wght.ttf", "NotoSerifHebrew-wdth-wght.ttf"),
    ("Heebo-wght.ttf", "Alef-Regular.ttf"),
    ("NotoRashiHebrew-wght.ttf", "DavidLibre-Regular.ttf"),
)
FAMILIES = {
    "Duplex transmission": ("flatbed_old", (250, 240, 221)),
    "Platen and photocopy": ("adobe_scan", (237, 237, 234)),
    "Bound book": ("flatbed_old", (235, 241, 224)),
    "Handheld phone": ("phone_oblique", (247, 239, 229)),
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def font(name, size):
    return ImageFont.truetype(FONTS / name, size, layout_engine=ImageFont.Layout.RAQM)


def rtl_line(draw, text, y, right, left, name, size, word_gap, ink):
    """Place whole RTL words with explicit space widths and no line wrapping."""
    words = text.split(" ")
    while size > 15:
        face = font(name, size)
        widths = [face.getlength(word, direction="rtl") for word in words]
        gap = face.getlength(" ") * word_gap
        if sum(widths) + gap * (len(words) - 1) <= right - left - 8:
            break
        size -= 1
    else:
        raise ValueError("Text does not fit on a single line")
    start = right
    boxes = []
    for word, width in zip(words, widths):
        box = draw.textbbox((right, y), word, font=face, direction="rtl", anchor="rs")
        if box[0] < left or box[1] < 0 or box[2] > W or box[3] > H:
            raise ValueError("Text bounds outside the layout")
        draw.text((right, y), word, font=face, direction="rtl", anchor="rs", fill=ink)
        boxes.append(box)
        right -= width + gap
    return {
        "text": text,
        "label_sha256": sha256(text.encode()).hexdigest(),
        "font": name,
        "size_px": size,
        "word_gap_px": round(gap, 2),
        "baseline": y,
        "right_anchor": start,
        "box_xyxy": [
            int(np.floor(min(b[0] for b in boxes))),
            int(np.floor(min(b[1] for b in boxes))),
            int(np.ceil(max(b[2] for b in boxes))),
            int(np.ceil(max(b[3] for b in boxes))),
        ],
    }


def recto(heading, body, *, family, style, treated):
    paper = FAMILIES[family][1] if treated else (254, 254, 253)
    img = Image.new("RGB", (W, H), paper)
    draw = ImageDraw.Draw(img)
    title_font, body_font = FONT_PAIRS[style] if treated else (CONTROL_FONT,) * 2
    title_size = (48, 53, 58, 43, 52)[style] if treated else 43
    body_size = (30, 27, 32, 25, 29)[style] if treated else 28
    leading = (72, 83, 64, 92, 76)[style] if treated else 76
    word_gap = (0.80, 1.28, 1.12, 1.60, 0.92)[style] if treated else 1.0
    left = 130 if family == "Bound book" else 108
    right = W - (145 if family == "Bound book" else 109)
    title_y = 235
    line_ys = [344 + n * leading + (25 if n >= 4 else 0) for n in range(8)]
    ink = ((31, 35, 34), (39, 35, 33), (42, 40, 36), (32, 45, 54), (45, 37, 42))[style] if treated else (31, 32, 32)
    rule = tuple((x + p) // 2 for x, p in zip(ink, paper))

    draw.line((left, 160, right, 160), fill=rule, width=2)
    draw.line((right - 96, 160, right, 160), fill=ink, width=4)
    draw.line((left, 267, right, 267), fill=rule, width=2)
    if family == "Platen and photocopy":
        for y in line_ys:
            draw.line((left - 12, y + 20, right + 14, y + 20), fill=rule, width=1)
    if family == "Bound book":
        draw.line((right + 23, 292, right + 23, line_ys[-1] + 17), fill=rule, width=1)
    if family == "Handheld phone":
        draw.rounded_rectangle((left - 22, 286, right + 22, line_ys[-1] + 30), 8, outline=rule)
    draw.line((left, 1090, right, 1090), fill=rule, width=2)
    labels = [rtl_line(draw, heading, title_y, right, left, title_font, title_size, word_gap, ink)]
    for n, (y, line) in enumerate(zip(line_ys, body)):
        name = title_font if treated and n in (0, 4) else body_font
        size = body_size + (3 if treated and n in (0, 4) else 0)
        inset = 22 if n % 4 == 3 else 0
        labels.append(rtl_line(draw, line, y, right - inset, left, name, size, word_gap, ink))
    return img, labels


def reverse_page(lines, shift):
    image = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(image)
    ordered = lines[shift:] + lines[:shift]
    for n, line in enumerate(ordered):
        rtl_line(draw, line, 298 + 79 * n, W - 150, 140,
                 "DavidLibre-Regular.ttf", 30, 1.02, (7, 7, 7))
    return image


def corner_tone(image, seed, strength):
    """Smooth nonuniform paper field under a fine, patchy sensor layer."""
    rng = np.random.default_rng(seed)
    knots = rng.uniform(0, 1, (7, 5)).astype(np.float32)
    field = cv2.resize(knots, image.size, interpolation=cv2.INTER_CUBIC)
    blend = 1 - strength * np.clip(field, 0, 1)
    return Image.fromarray(np.rint(np.asarray(image) * blend[..., None]).astype(np.uint8))


def platen(image, style):
    """Reproduce screened ink and a hard scanner edge, with bars in the margin."""
    gray = np.asarray(image.convert("L"))
    screen = np.array([[0, 2], [3, 1]], dtype=np.int16)
    phase = np.tile(screen, (H // 2, W // 2))
    stepped = np.clip((gray.astype(np.int16) + phase * 9 - 13) // 29 * 29, 0, 255)
    im = Image.fromarray(stepped.astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(im)
    band = 13 + 7 * style
    draw.rectangle((0, 0, W - 1, 3 + style), fill=(15, 14, 14))
    draw.rectangle((0, 0, band, H - 1), fill=(16, 16, 15))
    x = W - 26 - 7 * style
    draw.rectangle((x, 0, x + 3 + style, H - 1), fill=(24, 23, 23))
    return im


def bound_gutter(image, labels, seed, style):
    """A broad soft falloff and a dark binding fringe."""
    rgb = np.asarray(image)
    x = np.linspace(1, 0, W, dtype=np.float32)
    gain = 1 - (0.45 + 0.05 * style) * np.exp(-x / 0.10)
    image = Image.fromarray(np.rint(rgb * gain[None, :, None]).astype(np.uint8))
    box = (
        min(l["box_xyxy"][0] for l in labels), min(l["box_xyxy"][1] for l in labels),
        max(l["box_xyxy"][2] for l in labels), max(l["box_xyxy"][3] for l in labels),
    )
    return soft_scanner_edge(image, seed, side="right", width_fraction=0.035 + 0.008 * style,
                             darkness=0.91, feather_px=10, text_box=box, taper=0.026)


def phone(image, style, labels):
    """Project the front onto a synthetic desk plane and check all line corners."""
    top = 61 + 12 * style
    dst = np.float32([[49, top], [W - 44 - 7 * style, 52], [W - 27, H - 53], [63 + 8 * style, H - 32]])
    src = np.float32([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]])
    warp = cv2.getPerspectiveTransform(src, dst)
    for line in labels:
        l, t, r, b = line["box_xyxy"]
        polygon = cv2.perspectiveTransform(np.float32([[[l, t], [r, t], [r, b], [l, b]]]), warp)[0]
        if np.any(polygon < 0) or np.any(polygon >= [W, H]):
            raise ValueError("Phone frame clipped a label")
        line["capture_polygon"] = polygon.round(2).tolist()
    rgb = cv2.warpPerspective(np.asarray(image.filter(ImageFilter.GaussianBlur(0.2))), warp, image.size)
    mask = cv2.warpPerspective(np.full((H, W), 255, np.uint8), warp, image.size)
    shadow = cv2.GaussianBlur(np.roll(mask, (11, 9), axis=(0, 1)), (0, 0), 11) / 255
    y, x = np.ogrid[:H, :W]
    desk = 44 + 17 * y / H + 12 * x / W
    desk = (desk * (1 - 0.41 * shadow))[..., None] * np.array([0.99, 1.02, 1.07])
    return Image.fromarray(np.where(mask[..., None] > 127, rgb, desk).astype(np.uint8))


def capture(image, reverse, labels, family, style, seed, base):
    image = apply_profile(image, base, seed=seed)
    image = corner_tone(image, seed + 1, 0.037 + 0.014 * style)
    if family == "Duplex transmission":
        opacity = 0.09 + 0.025 * style
        image = show_through(image, reverse, seed + 2, opacity=(opacity, opacity),
                             blur_px=(1.25, 1.85), offset_fraction=(-0.025, 0.025),
                             transmission_variation=0.45)
    if family == "Platen and photocopy":
        image = platen(image, style)
    if family == "Bound book":
        image = show_through(image, reverse, seed + 2, opacity=(0.055, 0.075),
                             blur_px=(1.2, 1.6), transmission_variation=0.30)
        image = bound_gutter(image, labels, seed + 3, style)
    image = spatial_noise(image, seed + 4, sigma=(3 + style, 4 + style), variation=(0.77, 0.77))
    return phone(image, style, labels) if family == "Handheld phone" else image


def build(output):
    if not features.check_feature("raqm"):
        raise RuntimeError("Pillow with libraqm is required")
    copy_path = HERE / "copy.json"
    copy = json.loads(copy_path.read_bytes())
    text = copy["headings"] + sum(copy["blocks"], []) + copy["verso"]
    if len(text) != 60 or len(set(text)) != 60 or not all(unicodedata.is_normalized("NFC", s) for s in text):
        raise ValueError("Expected 60 distinct NFC text lines")
    output.mkdir(parents=True)
    manifest = {
        "schema": "heocr.scanifier_realism_preview.v1",
        "licence": "CC0-1.0",
        "purpose": "synthetic visual preview",
        "rtl": True,
        "dimensions": [W, H],
        "copy_sha256": digest(copy_path),
        "generator_sha256": digest(Path(__file__)),
        "pairs": [],
    }
    used_fonts = {CONTROL_FONT, *(name for pair in FONT_PAIRS for name in pair)}
    manifest["fonts"] = {f: digest(FONTS / f) for f in sorted(used_fonts)}
    for idx, (family, (preset, _)) in enumerate(FAMILIES.items()):
        path = PRESETS / f"{preset}.json"
        base = read_profile(path)
        for style in range(5):
            number = 1 + idx * 5 + style
            seed = 260112400 + number * 10
            block = copy["blocks"][(idx + style) % 4]
            heading = copy["headings"][number - 1]
            reverse = reverse_page(copy["verso"], style)
            clean, control_lines = recto(heading, block, family=family, style=style, treated=False)
            bold, treated_lines = recto(heading, block, family=family, style=style, treated=True)
            treated = capture(bold, reverse, treated_lines, family, style, seed, base)
            pair = {"id": f"{number:02}", "family": family, "style": style + 1,
                    "seed": seed, "preset": path.name, "preset_sha256": digest(path)}
            for arm, img, lines in (("control", clean, control_lines), ("preview", treated, treated_lines)):
                name = f"pair-{number:02}-{arm}.jpg"
                quality = (84 - style * 4) if arm == "preview" and family == "Handheld phone" else 91
                img.save(output / name, format="JPEG", quality=quality, subsampling=0)
                pair[arm] = {"image": f"images/{name}", "sha256": digest(output / name), "lines": lines}
            manifest["pairs"].append(pair)
    (output.parent / "generation_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "images")
    build(parser.parse_args().output)
