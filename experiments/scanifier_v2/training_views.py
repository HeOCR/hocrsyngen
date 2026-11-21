"""Render fixed-geometry training views from one complete DEV capture fit."""
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageChops

from .degradations import scanner_edge_bars, show_through
from .dev_profiles import apply_profile, validate_profile

_STAGES = ('select', 'raster', 'duplex', 'edge')
_OVERLAYS = ('show_through_opacity', 'scanner_edge_fraction', 'scanner_bar_fraction', 'scanner_bars')


@dataclass(frozen=True)
class FittedCapture:
    name: str
    base: dict
    duplex: dict | None
    edge: dict | None
    hashes: dict


def read_training_fit(name, base, *, duplex=None, edge=None):
    """Read the frozen components of one capture fit and record their byte hashes."""
    if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
        raise ValueError('invalid capture fit name')
    base = Path(base)
    hashes = {}

    def read(path, stage):
        path = Path(path)
        if path.resolve().parent != base.resolve().parent:
            raise ValueError('each overlay must be bundled with its matching base fit')
        raw = path.read_bytes()
        hashes[stage] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    profile = read(base, 'raster')
    validate_profile(profile)
    if profile['status'] != 'dev_fit' or any(any(profile['ranges'][field]) for field in _OVERLAYS):
        raise ValueError('training views require a DEV fit with explicitly supplied overlays')
    reverse_args = read(duplex, 'duplex')['ranges'] if duplex is not None else None
    edge_args = read(edge, 'edge')['scanner_kwargs'] if edge is not None else None
    if edge_args is not None and tuple(edge_args.get('bar_count', ())) != (0, 0):
        raise ValueError('interior scanner bars need their own calibrated training fit')
    return FittedCapture(name, profile, reverse_args, edge_args, hashes)


def render_training_view(image, fits, *, recipe_version, bank_seed, source_sha256, page_index,
                         view_index, attempt=0, reverse=None, include_edge=False, protected_boxes=()):
    """Apply a complete ordered-bank fit and return a raster and provenance.

    The reverse is a cleared, registered back raster in normal reading
    orientation. Protected boxes are annotated front regions in pixel edges.
    """
    if not fits or not isinstance(recipe_version, str) or not recipe_version:
        raise ValueError('an ordered capture bank and recipe version are required')
    if not isinstance(source_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', source_sha256):
        raise ValueError('source_sha256 must be the input asset digest')
    if any(type(value) is not int or value < 0 for value in (bank_seed, page_index, view_index, attempt)):
        raise ValueError('bank seed, indexes and attempt must be nonnegative integers')
    if reverse is not None and reverse.size != image.size:
        raise ValueError('register the reverse to the front dimensions before rendering')

    seed_material = [recipe_version, bank_seed, source_sha256, page_index, view_index, attempt]
    seeds = {}
    for stage in _STAGES:
        raw = json.dumps([*seed_material, stage], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        seeds[stage] = int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big')
    fit = fits[seeds['select'] % len(fits)]
    page = apply_profile(image, fit.base, seed=seeds['raster'])
    applied = ['raster']
    reverse_sha256 = None
    if fit.duplex is not None and reverse is not None:
        args = fit.duplex
        blur = tuple(min(20, max(page.size) * value) for value in args['blur_fraction_long_edge'])
        page = show_through(page, reverse, seeds['duplex'], opacity=args['opacity'],
                            blur_px=blur, offset_fraction=args['offset_fraction'])
        applied.append('duplex')
        reverse_sha256 = hashlib.sha256(reverse.convert('RGB').tobytes()).hexdigest()
    if fit.edge is not None and include_edge:
        boxes = tuple(protected_boxes)
        if not boxes or any(not _inside(box, page.size) for box in boxes):
            raise ValueError('the scanner edge needs valid protected boxes')
        edged = scanner_edge_bars(page, seeds['edge'], **fit.edge)
        changed = ImageChops.difference(page, edged)
        if any(changed.crop(box).getbbox() is not None for box in boxes):
            raise ValueError('the scanner edge intersects a protected annotation')
        page = edged
        applied.append('edge')
    provenance = dict(recipe_version=recipe_version, bank_seed=bank_seed, source_sha256=source_sha256,
                      page_index=page_index, view_index=view_index, attempt=attempt, fit=fit.name,
                      fit_hashes=fit.hashes, stage_seeds=seeds, stages=applied, size=list(page.size),
                      reverse_rgb_sha256=reverse_sha256, rgb_sha256=hashlib.sha256(page.tobytes()).hexdigest())
    return page, provenance


def _inside(box, size):
    if len(box) != 4 or any(type(value) is not int for value in box):
        return False
    left, top, right, bottom = box
    return 0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]
