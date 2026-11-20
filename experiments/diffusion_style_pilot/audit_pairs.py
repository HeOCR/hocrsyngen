"""Reconstruct a seeded, blinded audit of the GPU job's accepted image pairs."""
import argparse
import hashlib
import json
from pathlib import Path

from contracts import ID, file_under, read_records, sha256, write_json
from level2 import CONFUSABLES
from paper import SEED, pair, read_gray, read_tiles, write_gray


def select_pairs(records, labels):
    ranked = sorted(records, key=lambda row: hashlib.sha256(f'{SEED}:audit:{row["id"]}'.encode()).digest())
    picked = {}
    for char in set(''.join(CONFUSABLES)):
        first = next((row for row in ranked if char in labels[row['id']]), None)
        if first is None:
            raise ValueError('Accepted lines cannot cover the confusion characters')
        picked[first['id']] = first
    for row in ranked:
        if len(picked) == 50:
            break
        picked[row['id']] = row
    if len(picked) != 50:
        raise ValueError('Expected 50 accepted pairs for the blinded audit')
    return [row for row in ranked if row['id'] in picked]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Original GPU job input directory')
    parser.add_argument('result', type=Path, help='Verified GPU job result directory')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source, result, output = (path.resolve() for path in (args.input, args.result, args.output))
    manifest = file_under(result, 'pairs.jsonl')
    rows = read_records(manifest)
    fit = json.loads(file_under(result, 'paper-fit.json').read_text())
    labels_path = file_under(source, 'train-labels.jsonl')
    if sha256(labels_path) != fit['label_manifest_sha256']:
        raise ValueError('Audit labels differ from the GPU job labels')
    labels = {row['id']: row['text'] for row in read_records(labels_path)}
    tiles = read_tiles(file_under(result, 'paper-tiles.jsonl'))
    picked = select_pairs(rows, labels)
    (output / 'blind').mkdir(parents=True, exist_ok=False)
    key = []
    for n, row in enumerate(picked, start=1):
        item = row['id']
        if not ID.fullmatch(item) or row['label_sha256'] != item:
            raise ValueError('Invalid audited pair ID')
        original = read_gray(file_under(source, f'render/lines/{item}.png'))
        plain, styled, mask = pair(original, tiles, item)
        if mask != row['mask_sha256']:
            raise ValueError('Audit image mask differs from the GPU job mask')
        for arm, pixels in (('control', plain), ('texture', styled)):
            if hashlib.sha256(pixels.tobytes()).hexdigest() != row[arm]['pixels_sha256']:
                raise ValueError('Reconstructed pixels differ from the GPU job')
        flipped = bytes.fromhex(item)[0] % 2
        ordered = (('texture', styled), ('control', plain)) if flipped else (('control', plain), ('texture', styled))
        slots = {}
        for slot, (arm, image) in zip('AB', ordered):
            filename = f'{n:03d}-{slot}.png'
            write_gray(output / 'blind' / filename, image)
            slots[filename] = arm
        key.append({'id': item, 'text': labels[item], 'slots': slots})
    write_json(output / 'review-key.json', {'pairs_sha256': sha256(manifest), 'pairs': key})


if __name__ == '__main__':
    main()
