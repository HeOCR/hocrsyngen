import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from experiments.scanifier_v2.training_views import read_training_fit, render_training_view


PRESET = Path(__file__).parents[1] / 'experiments/scanifier_v2/presets/archive_old.json'
SEED = dict(recipe_version='qa1', bank_seed=22, source_sha256='a'*64, page_index=0, view_index=1)


def config(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def fit_files(tmp_path):
    profile = json.loads(PRESET.read_bytes())
    profile['jpeg_encoders'] = []
    return config(tmp_path / 'base.json', profile), config(tmp_path / 'duplex.json', {
        'ranges': {'opacity': [0.08, 0.08], 'blur_fraction_long_edge': [0, 0], 'offset_fraction': [0, 0]},
    })


def test_duplex_protects_geometry_and_keeps_raster_seed(tmp_path):
    base, duplex = fit_files(tmp_path)
    fit = read_training_fit('paired', base, duplex=duplex)
    front = Image.new('RGB', (256, 200), 'white')
    reverse = front.copy()
    ImageDraw.Draw(reverse).rectangle((8, 30, 55, 90), fill='black')
    clean, clean_meta = render_training_view(front, [fit], **SEED)
    placed, paired = render_training_view(front, [fit], reverse=reverse, **SEED)
    repeated, repeated_meta = render_training_view(front, [fit], reverse=reverse, **SEED)
    assert placed.size == repeated.size == front.size
    assert paired == repeated_meta and placed.tobytes() == repeated.tobytes()
    assert paired['stages'] == ['raster', 'duplex']
    assert paired['stage_seeds'] == clean_meta['stage_seeds']
    assert ImageChops.difference(clean, placed).getbbox() == (200, 30, 248, 91)
    with pytest.raises(ValueError, match='register the reverse'):
        render_training_view(front, [fit], reverse=reverse.resize((250, 200)), **SEED)


def test_scanner_edge_refuses_a_box_intersection(tmp_path):
    base, _ = fit_files(tmp_path)
    edge = config(tmp_path / 'edge.json', {'scanner_kwargs': {
        'edge_sides': ['left'], 'edge_fraction': [0.08, 0.08], 'edge_taper': [0, 0],
        'edge_darkness': [1, 1], 'bar_count': [0, 0], 'feather_px': [0, 0],
    }})
    fit = read_training_fit('archive', base, edge=edge)
    front = Image.new('RGB', (256, 200), 'white')
    _, meta = render_training_view(front, [fit], include_edge=True, protected_boxes=[(32, 20, 190, 180)], **SEED)
    assert meta['stages'] == ['raster', 'edge']
    with pytest.raises(ValueError, match='intersects'):
        render_training_view(front, [fit], include_edge=True, protected_boxes=[(5, 20, 190, 180)], **SEED)


def test_priors_and_separate_overlay_bundles_are_refused(tmp_path):
    base, duplex = fit_files(tmp_path)
    other = tmp_path / 'other'; other.mkdir()
    elsewhere = other / 'duplex.json'; elsewhere.write_bytes(duplex.read_bytes())
    with pytest.raises(ValueError, match='matching base'):
        read_training_fit('paired', base, duplex=elsewhere)
    profile = json.loads(base.read_bytes()); profile['status'] = 'prior_only'
    with pytest.raises(ValueError, match='DEV fit'):
        read_training_fit('prior', config(base, profile))
