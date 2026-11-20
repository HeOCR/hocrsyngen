"""Reconstruct and encode the GPU-approved pairs for the CPU training job."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from audit_pairs import read_blend_inputs, reconstruct
from contracts import ARMS, file_under, sha256, write_json
from level2 import encode, tess_training_config
from paper import write_gray


def encode_pair(source, staging, scratch, row, label, tiles):
    plain, styled = reconstruct(source, row, tiles)
    for arm, image in zip(ARMS, (plain, styled)):
        png = scratch / f'{row["id"]}-{arm}.png'
        write_gray(png, image)
        encoding = staging / 'paired' / arm / f'{row["id"]}.lstmf'
        if not encode(png, label, encoding, source / 'tessdata'):
            raise RuntimeError(f'Encoding failed for {row["id"]} ({arm})')
        row[arm].update(lstmf=encoding.relative_to(staging).as_posix(), sha256=sha256(encoding))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('result', type=Path)
    parser.add_argument('audit', type=Path)
    parser.add_argument('output', type=Path, help='Fresh directory for CPU job training assets')
    args = parser.parse_args()
    source, result, output = (p.resolve() for p in (args.source, args.result, args.output))
    if output.exists():
        raise ValueError('Use a fresh staging directory')
    if not subprocess.check_output(['tesseract', '--version'], text=True).startswith('tesseract 5.5.3\n'):
        raise RuntimeError('Pair encoding requires Tesseract 5.5.3')
    tess_training_config()
    os.environ['OMP_THREAD_LIMIT'] = '1'
    manifest, rows, labels, tiles = read_blend_inputs(source, result)
    if not 500 <= len(rows) <= 1000 or len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Accepted manifest has duplicate IDs or an unexpected size')
    audit = json.loads(args.audit.read_text())
    accepted_digest = sha256(manifest)
    if (audit['accepted_sha256'] != accepted_digest or audit['status'] != 'PASS'
            or not audit['record'] or audit['examined_pairs'] != 50):
        raise ValueError('Pair encoding requires the verified, blinded 50-pair audit')
    assets_path = file_under(source, 'assets.json')
    fit = json.loads(file_under(result, 'paper-fit.json').read_text())
    if sha256(assets_path) != fit['assets_sha256']:
        raise ValueError('Asset lock diverges from the GPU job')
    stock = file_under(source, 'tessdata/heb.traineddata')
    assets = json.loads(assets_path.read_text())
    if sha256(stock) != assets['tessdata/heb.traineddata']:
        raise ValueError('Stock weights diverge from the GPU job')
    with TemporaryDirectory(dir=output.parent) as tmp:
        temp = Path(tmp)
        staging = temp / 'input'
        scratch = temp / 'images'
        scratch.mkdir()
        for arm in ARMS:
            (staging / 'paired' / arm).mkdir(parents=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            encoded = list(pool.map(lambda row: encode_pair(source, staging, scratch, row, labels[row['id']], tiles), rows))
        pair_manifest = staging / 'pairs.jsonl'
        pair_manifest.write_text(''.join(json.dumps(row) + '\n' for row in encoded))
        write_json(staging / 'pair-audit.json', {**audit, 'sha256': sha256(pair_manifest)})
        write_json(staging / 'assets.json', {'tessdata/heb.traineddata': assets['tessdata/heb.traineddata']})
        (staging / 'tessdata').mkdir()
        shutil.copyfile(stock, staging / 'tessdata/heb.traineddata')
        staging.rename(output)


if __name__ == '__main__':
    main()
