"""Replay three private DEV fits on an invented page and save a QA sheet locally."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

from hocrsyngen.assets import synthetic_data_path

from .dev_profiles import apply_profile
from .training_views import read_training_fit, render_training_view


def invented_leaf():
    font_path = synthetic_data_path('fonts/Alef-Regular.ttf')
    body = ImageFont.truetype(str(font_path), 34)
    page = Image.new('RGB', (1100, 1500), 'white')
    front = ImageDraw.Draw(page)
    boxes = []
    for i, label in enumerate(('נסיון דפוס קטן', 'מרווח בין שורות', 'סימני דפוס ישן', 'מספר שורות לדוגמה') * 3):
        point = (940, 145 + i * 87)
        boxes.append(front.textbbox(point, label, font=body, anchor='ra', direction='rtl'))
        front.text(point, label, font=body, anchor='ra', direction='rtl', fill='#151413')
    reverse = Image.new('RGB', page.size, 'white')
    back = ImageDraw.Draw(reverse)
    for i in range(9):
        back.text((230, 210 + i * 110), 'דוגמת מעבר דיו', font=body, direction='rtl', fill='black')
    return page, reverse, boxes, font_path


def noise_probe(fit, seed):
    blank = Image.new('RGB', (440, 320), 'white')
    quiet = fit.base | {'ranges': fit.base['ranges'] | {'noise_sd': [0, 0]}}
    noisy = np.asarray(apply_profile(blank, fit.base, seed=seed).convert('L'), dtype=np.float32)
    control = np.asarray(apply_profile(blank, quiet, seed=seed).convert('L'), dtype=np.float32)
    residual = noisy - control
    patch_sd = [float(patch.std()) for row in np.split(residual, 4) for patch in np.split(row, 4, axis=1)]
    preview = Image.fromarray(np.uint8(np.clip(127 + 12 * residual, 0, 255)))
    return preview, [round(min(patch_sd), 3), round(max(patch_sd), 3)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fits', type=Path, help='private green, stuart and gazette fit folders')
    parser.add_argument('output', type=Path, help='new private output directory')
    args = parser.parse_args()
    page, reverse, boxes, font_path = invented_leaf()
    font = ImageFont.truetype(str(font_path), 24)
    title = ImageFont.truetype(str(font_path), 34)
    sheet = Image.new('RGB', (1000, 1180), '#ecebe5')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 16), 'Scanifier training capture QA', font=title, fill='#172124')
    draw.text((24, 61), 'Same invented front · frozen non-test development fits', font=font, fill='#34484b')
    for x, text in ((24, 'Fitted raster'), (287, 'With matched overlay'), (550, 'Overlay difference ×8')):
        draw.text((x, 109), text, font=font, fill='#172124')
    rows = []
    for index, name in enumerate(('green', 'stuart', 'gazette')):
        folder = args.fits / name
        kwargs = {'edge': folder / 'edge.json'} if name == 'gazette' else {'duplex': folder / 'duplex.json'}
        fit = read_training_fit(name, folder / 'base.json', **kwargs)
        seeds = dict(recipe_version='training-qa-v1', bank_seed=561201, page_index=0, view_index=0,
                     source_sha256=hashlib.sha256(page.tobytes()).hexdigest())
        base, _ = render_training_view(page, [fit], **seeds)
        rendered, provenance = render_training_view(page, [fit], **seeds, reverse=reverse,
                                                   include_edge=True, protected_boxes=boxes)
        difference = ImageChops.difference(base, rendered).convert('L')
        bbox = difference.getbbox()
        if bbox is None or base.size != page.size or rendered.size != page.size:
            raise ValueError(f'{name} QA requires a visible overlay and fixed geometry')
        y = 143 + index * 342
        for x, asset in ((24, base), (287, rendered)):
            sheet.paste(asset.resize((224, 306), Image.Resampling.LANCZOS), (x, y))
        array = np.asarray(difference)
        row, col = np.unravel_index(array.argmax(), array.shape)
        left = min(max(int(col)-110, 0), page.width-220)
        top = min(max(int(row)-70, 0), page.height-140)
        detail = difference.crop((left, top, left+220, top+140)).point(lambda value: min(255, 8*value))
        sheet.paste(detail.resize((400, 180), Image.Resampling.NEAREST), (550, y))
        noise, levels = noise_probe(fit, provenance['stage_seeds']['raster'])
        draw.text((550, y+184), 'Amplified flat-patch noise', font=font, fill='#34484b')
        sheet.paste(noise.crop((0, 0, 440, 55)).resize((400, 50)), (550, y+212))
        stage = provenance['stages'][-1]
        draw.text((550, y+264), f'{name.title()} · {stage}', font=font, fill='#172124')
        draw.text((550, y+295), f'Local noise SD {levels[0]}–{levels[1]} levels', font=font, fill='#34484b')
        rows.append(provenance | {'overlay_bbox': list(bbox), 'overlay_peak_luma_levels': int(array.max()),
                                  'overlay_changed_pixels': int(np.count_nonzero(array)),
                                  'noise_patch_sd_range_luma_levels': levels, 'protected_boxes': boxes})
    args.output.mkdir(mode=0o700)
    sheet.save(args.output / 'dev-qa-sheet.png')
    (args.output / 'dev-qa.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
