#!/usr/bin/env python3
"""Development probe for pointed Hebrew; run only on approved, unheld-out fonts.

Requires uharfbuzz, fonttools and Pillow with RAQM. Geometry is a triage signal,
not typographic approval. See docs/niqqud_fonts.md.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import uharfbuzz as hb
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, features
from hocrsyngen.font_exclusion import check_font, is_excluded

# Synthetic letter/mark combinations, not corpus text. Include every standard
# niqqud point, both holams, qamats qatan, shin/sin and accent stacking.
CASES = [(f"point-{cp:04X}", "ב" + chr(cp) + "ג") for cp in
         list(range(0x05B0, 0x05BA)) + [0x05BA, 0x05BB, 0x05BC, 0x05BD, 0x05BF, 0x05C1, 0x05C2, 0x05C7]]
CASES += [("shin-shin", "שַׁג"), ("shin-sin", "שַׂג"),
          ("dagesh-vowel", "בָּג"), ("holam-male", "בּוֹג"),
          ("holam-haser", "בוֺג"), ("qamats-qatan", "בׇּג"),
          ("above-stack", "בַּ֨ג"), ("below-stack", "בָּ֖ג")]
ABOVE = {0x05B9, 0x05BA, 0x05BF, 0x05C1, 0x05C2}
BELOW = set(range(0x05B0, 0x05B9)) | {0x05BB, 0x05BD, 0x05C7}


def inspect(path):
    # Explicitly refuse even if an evaluation bypass is present.
    if os.environ.get('HOCRSYNGEN_EVAL_RENDER') == '1' or is_excluded(path):
        raise ValueError('held-out fonts and evaluation bypass are forbidden')
    check_font(path)
    data = path.read_bytes()
    face = hb.Face(data)
    font = hb.Font(face)
    font.scale = (face.upem, face.upem)
    tt = TTFont(path)
    for record in tt['name'].names:
        if record.nameID in (1, 4, 6, 16):
            name = record.toUnicode()
            if is_excluded(name):
                raise ValueError('held-out font family in font name table')
            check_font(name)
    cmap = tt.getBestCmap()
    dotted = font.get_nominal_glyph(0x25CC)
    results = []
    for label, text in CASES:
        missing = [f'U+{ord(c):04X}' for c in text if ord(c) not in cmap]
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        infos, positions = buf.glyph_infos, buf.glyph_positions
        errors = [f'missing {c}' for c in missing]
        if any(g.codepoint == 0 for g in infos):
            errors.append('.notdef')
        if dotted and any(g.codepoint == dotted for g in infos):
            errors.append('dotted circle')
        # For the simple one-mark cases, identify the two base glyphs by
        # character clusters and the remaining zero-advance glyph as the mark.
        # Precomposed or substituted output is intentionally inconclusive.
        if label.startswith('point-') and not errors:
            mark_cp = ord(text[1])
            marked = [(i, p) for i, p in zip(infos, positions) if p.x_advance == 0]
            base = [(i, p) for i, p in zip(infos, positions) if i.cluster == 0 and p.x_advance != 0]
            if len(marked) != 1 or len(base) != 1:
                errors.append('geometry inconclusive (substitution or mark count)')
            else:
                # Calculate absolute boxes in shaped visual order.
                x = y = 0
                boxes = []
                for info, pos in zip(infos, positions):
                    e = font.get_glyph_extents(info.codepoint)
                    if e:
                        x1 = x + pos.x_offset + e.x_bearing
                        y1 = y + pos.y_offset + e.y_bearing
                        boxes.append((info, pos, (x1, y1 + e.height, x1 + e.width, y1)))
                    x += pos.x_advance; y += pos.y_advance
                m = next((b for b in boxes if b[0] is marked[0][0]), None)
                b = next((b for b in boxes if b[0] is base[0][0]), None)
                if not m or not b:
                    errors.append('geometry inconclusive (no glyph extents)')
                else:
                    mx1, my1, mx2, my2 = m[2]; bx1, by1, bx2, by2 = b[2]
                    if mark_cp in ABOVE and my2 < (by1 + by2) / 2:
                        errors.append('above mark too low')
                    if mark_cp in BELOW and my1 > (by1 + by2) / 2:
                        errors.append('below mark too high')
                    for other in boxes:
                        if other[1].x_advance and other[0].cluster != 0:
                            ox1, oy1, ox2, oy2 = other[2]
                            if min(mx2, ox2) > max(mx1, ox1) and min(my2, oy2) > max(my1, oy1):
                                errors.append('mark overlaps neighboring letter')
        if not label.startswith('point-') and not errors:
            errors.append('geometry and mark identity not checked for combinations')
        results.append({'case': label, 'text': text, 'issues': errors})
    return {'font': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'cases': results}


def sheet(path, result, output):
    if not features.check_feature('raqm'):
        raise RuntimeError('Pillow requires libraqm')
    image = Image.new('RGB', (850, 60 + 44 * len(CASES)), 'white')
    draw = ImageDraw.Draw(image)
    label_font = ImageFont.load_default()
    hebrew = ImageFont.truetype(str(path), 31, layout_engine=ImageFont.Layout.RAQM)
    draw.text((12, 10), path.name + '  ' + result['sha256'][:16], fill='black', font=label_font)
    for n, case in enumerate(result['cases']):
        y = 45 + 44*n
        draw.text((12, y), case['case'] + ('  !' if case['issues'] else ''), fill='black', font=label_font)
        draw.text((500, y), case['text'], fill='black', font=hebrew, direction='rtl', language='he')
    image.save(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fonts', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for path in args.fonts:
        result = inspect(path)
        (args.output / (path.stem + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        sheet(path, result, args.output / (path.stem + '.png'))

if __name__ == '__main__':
    main()
