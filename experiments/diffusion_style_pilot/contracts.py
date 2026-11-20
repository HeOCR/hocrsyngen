"""File contracts shared by the two standalone pilot jobs."""
import hashlib
import json
from pathlib import Path
import re

ARMS = ('control', 'texture')
ID = re.compile(r'[a-f0-9]{64}')


def sha256(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def file_under(root, relative):
    root = root.resolve(strict=True)
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected a relative, portable input path')
    resolved = (root / path).resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('Input does not resolve to a regular file under the staging root')
    return resolved
