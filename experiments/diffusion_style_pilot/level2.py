"""Prepare paired OCR training inputs from governed, unpointed line renders."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
from functools import cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

import numpy as np

from contracts import ARMS, ID, file_under, read_records, sha256, write_json
from paper import SEED, SIDE, fit, pair, read_gray, read_tiles, write_gray, write_tiles

CONFUSABLES = ('הח', 'דר', 'בכ', 'וי', 'וז')
LABEL = re.compile(r'[א-ת ,.?!:;]{20,60}')


def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).split())


def validate_attestation(root, name):
    path = file_under(root, f'{name}.jsonl')
    decision = json.loads(file_under(root, 'attestations.json').read_text())[name]
    expected = 'CLEAR' if name == 'style-crops' else 'CLEAN'
    if not decision['record'] or decision['status'] != expected or decision['sha256'] != sha256(path):
        raise ValueError(f'{name} requires recorded {expected} on the exact manifest')
    return read_records(path)


def input_crops(root):
    rows = validate_attestation(root, 'style-crops')
    if len({row['source_id'] for row in rows}) != 1:
        raise ValueError('The first paper model requires exactly one cleared edition')
    if not 512 <= len(rows) <= 1024 or not 16 <= len({row['page'] for row in rows}) <= 32:
        raise ValueError('Expected 512–1,024 crops from 16–32 pages')
    if len({row['sha256'] for row in rows}) != len(rows):
        raise ValueError('Paper crops contain duplicate digests')
    pixels = []
    for row in rows:
        crop = row['crop_xywh']
        if row['dpi'] != 300 or len(crop) != 4 or crop[2:] != [SIDE, SIDE] or min(crop) < 0:
            raise ValueError('Crop coordinates or resolution do not match the registered recipe')
        path = file_under(root, row['png'])
        if sha256(path) != row['sha256']:
            raise ValueError('Paper crop digest changed')
        tile = read_gray(path)
        if tile.shape != (SIDE, SIDE):
            raise ValueError('Paper crop is not 64×64')
        pixels.append(tile)
    crops = np.stack(pixels)
    if len(np.unique(crops)) <= 2:
        raise ValueError('Paper source appears binarized')
    return crops


def input_lines(root):
    rows = validate_attestation(root, 'train-labels')
    if len(rows) != 1000 or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Expected exactly 1,000 distinct candidate lines')
    render_rows = read_records(file_under(root, 'render/manifest.jsonl'))
    renders = {row['id']: row for row in render_rows}
    if len(render_rows) != len(renders) or set(renders) != {row['id'] for row in rows}:
        raise ValueError('Render and label manifests have different line IDs')
    for row in rows:
        label, line_id = row['text'], row['id']
        if not ID.fullmatch(line_id) or not LABEL.fullmatch(label) or label != normalize(label):
            raise ValueError('Line violates the unpointed label contract')
        if hashlib.sha256(label.encode()).hexdigest() != line_id:
            raise ValueError('ID does not match the exact label')
        rec = renders[line_id]
        if rec['preset'] != 'none' or rec['font_id'] not in ('frank-ruhl-libre', 'david-libre-regular'):
            raise ValueError('Expected the governed, undegraded line renderer configuration')
        expected = file_under(root, f'render/lines/{line_id}.gt.txt').read_text(encoding='utf-8').rstrip('\n')
        if label != expected:
            raise ValueError('Line label disagrees with the render')
    return sorted(rows, key=lambda row: hashlib.sha256(f'{SEED}:{row["text"]}'.encode()).digest())


def read_tesseract(paths, tessdata, work):
    listing = work / 'reader-inputs.txt'
    listing.write_text(''.join(f'{p}\n' for p in paths))
    command = ['tesseract', str(listing), 'stdout', '--tessdata-dir', str(tessdata),
               '-l', 'heb', '--oem', '1', '--psm', '13', '-c', 'page_separator=\f']
    result = subprocess.run(command, capture_output=True, encoding='utf-8', check=True)
    pages = result.stdout.split('\f')
    if len(pages) == len(paths) + 1 and pages[-1] == '':
        pages.pop()
    if len(pages) != len(paths):
        raise RuntimeError('Tesseract did not return one page slot per input line')
    return list(map(normalize, pages))


def read_onnx(paths, models):
    from paddleocr_hebrew.plan_e_rec import PlanECascade

    names = [models / 'server-svtrv2' / f for f in ('ctc.onnx', 'nrtr-encoder.onnx', 'nrtr-decstep.onnx')]
    dictionary = models / 'charset_v2f.txt'
    reader = PlanECascade(*map(str, names), str(dictionary), providers=['CPUExecutionProvider'])
    output = []
    for start in range(0, len(paths), 16):
        images = [np.repeat(read_gray(path)[..., None], 3, axis=-1) for path in paths[start:start + 16]]
        output.extend(map(normalize, reader.rec_crops(images, mode='cascade')))
    if len(output) != len(paths):
        raise RuntimeError('Independent reader did not return one slot per input line')
    return output


def observed_swaps(expected, actual):
    swaps = set()
    edits = SequenceMatcher(a=expected, b=actual, autojunk=False).get_opcodes()
    for op, i, j, k, l in edits:
        if op == 'replace' and j - i == l - k:
            swaps.update(frozenset((a, b)) for a, b in zip(expected[i:j], actual[k:l]) if a != b)
    return swaps


@cache
def tess_training_config():
    installed = subprocess.check_output(['tesseract', '--list-langs'], encoding='utf-8')
    match = re.search(r'List of available languages in "([^"]+)"', installed)
    if not match:
        raise RuntimeError('Cannot locate the installed Tesseract configuration')
    return (Path(match.group(1)) / 'configs/lstm.train').resolve(strict=True)


def encode(image, label, output, tessdata):
    width, height = read_gray(image).shape[::-1]
    visual = label[::-1]
    image.with_suffix('.gt.txt').write_text(visual + '\n', encoding='utf-8')
    image.with_suffix('.box').write_text(
        f'WordStr 0 0 {width} {height} 0 #{visual}\n\t {width} {height} {width+1} {height+1} 0\n',
        encoding='utf-8',
    )
    result = subprocess.run(['tesseract', str(image), str(output.with_suffix('')),
                             '--tessdata-dir', str(tessdata), '-l', 'heb',
                             '--psm', '13', str(tess_training_config())], capture_output=True)
    return result.returncode == 0 and output.is_file() and output.stat().st_size > 0


def prepare_pairs(root, work, out, rows, tiles):
    for arm in ARMS:
        (work / arm).mkdir(parents=True, exist_ok=True)
    images, masks = [], {}
    for row in rows:
        line_id = row['id']
        render = read_gray(file_under(root, f'render/lines/{line_id}.png'))
        control, treatment, mask = pair(render, tiles, line_id)
        masks[line_id] = mask
        for arm, pixels in zip(ARMS, (control, treatment)):
            path = work / arm / f'{line_id}.png'
            write_gray(path, pixels)
            images.append(path)
    stock = read_tesseract(images, root / 'tessdata', work)
    independent = read_onnx(images, root / 'reader')
    reason = Counter()
    pair_counts = {pair: Counter() for pair in CONFUSABLES}
    accepted = []
    for i, row in enumerate(rows):
        line_id, label = row['id'], row['text']
        decoded = stock[2*i:2*i + 2] + independent[2*i:2*i + 2]
        swaps = set().union(*(observed_swaps(label, text) for text in decoded if text != label))
        for chars, counts in pair_counts.items():
            if set(chars) & set(label):
                counts['attempted'] += 1
                counts['reader_swap'] += int(frozenset(chars) in swaps)
        if any(text != label for text in decoded):
            reason['reader_mismatch'] += 1
            continue
        pair_images = images[2*i:2*i + 2]
        saved = {'id': line_id, 'label_sha256': line_id, 'mask_sha256': masks[line_id]}
        for arm, image in zip(ARMS, pair_images):
            saved[arm] = {'pixels_sha256': hashlib.sha256(read_gray(image).tobytes()).hexdigest()}
        accepted.append(saved)
    by_id = {row['id']: row['text'] for row in rows}
    coverage = set(''.join(by_id[row['id']] for row in accepted))
    accepted_fonts = {row['id']: row['font_id'] for row in read_records(root / 'render/manifest.jsonl')}
    supported = len({accepted_fonts[row['id']] for row in accepted}) == 2
    supported = supported and set(''.join(CONFUSABLES)) <= coverage
    with (out / 'accepted.jsonl').open('w') as handle:
        for row in accepted:
            handle.write(json.dumps(row) + '\n')
    write_json(out / 'quality.json', {'attempted': len(rows), 'accepted': len(accepted),
                                     'rejected': len(rows) - len(accepted), 'reasons': reason,
                                     'rejection_rate': (len(rows) - len(accepted)) / len(rows),
                                     'confusable_pairs': pair_counts, 'coverage_ok': supported})
    if len(accepted) < 500 or not supported:
        raise ValueError('The accepted pairs miss the registered volume or coverage floor')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    root, work, out = (p.resolve() for p in (args.root, args.work, args.out))
    rows = input_lines(root)
    crops = input_crops(root)
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    config_path = file_under(root, 'assets.json')
    assets = json.loads(config_path.read_text())
    for relative, digest in assets.items():
        if sha256(file_under(root, relative)) != digest:
            raise ValueError(f'Digest mismatch in pinned asset {relative}')
    expected = {'tessdata/heb.traineddata', 'reader/charset_v2f.txt'} | {
        f'reader/server-svtrv2/{name}' for name in ('ctc.onnx', 'nrtr-encoder.onnx', 'nrtr-decstep.onnx')}
    if not expected <= assets.keys():
        raise ValueError('Asset lock is missing a reader weight or dictionary')
    charset = set((root / 'reader/charset_v2f.txt').read_text().splitlines()) | {' '}
    if any(set(row['text']) - charset for row in rows):
        raise ValueError('Some labels contain characters outside the second reader charset')
    print('Fitting the scratch paper model.', flush=True)
    tiles, iterations, config = fit(crops, out / 'paper.safetensors')
    write_tiles(out / 'paper-tiles.jsonl', tiles)
    write_json(out / 'paper-fit.json', {'iterations': iterations, 'seed': SEED, 'config': config,
                                       'style_manifest_sha256': sha256(root / 'style-crops.jsonl'),
                                       'label_manifest_sha256': sha256(root / 'train-labels.jsonl'),
                                       'assets_sha256': sha256(config_path)})
    print('Checking both readers on the paired lines.', flush=True)
    prepare_pairs(root, work, out, rows, read_tiles(out / 'paper-tiles.jsonl'))


if __name__ == '__main__':
    main()
