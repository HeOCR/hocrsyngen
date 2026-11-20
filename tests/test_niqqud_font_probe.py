"""Tests for the optional font development probe and its opt-in registry."""
from pathlib import Path
import runpy

import pytest

from hocrsyngen.line_render import governed_faces

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / 'src/hocrsyngen/data/synthetic/fonts'


def test_v2_manifest_is_separate_and_pin_checked():
    v2 = governed_faces(FONTS / 'manifest.niqqud-v2.yaml')
    assert set(v2) == {'cardo-regular', 'ezra-sil-regular'}
    assert not set(v2) & set(governed_faces())
    assert all(face.license == 'OFL-1.1' for face in v2.values())


@pytest.fixture(scope='module')
def probe():
    pytest.importorskip('uharfbuzz')
    pytest.importorskip('fontTools')
    return runpy.run_path(str(ROOT / 'scripts/niqqud/check_fonts.py'))


def test_held_out_name_and_bypass_are_refused(probe, monkeypatch):
    monkeypatch.setenv('HOCRSYNGEN_EVAL_RENDER', '1')
    with pytest.raises(ValueError, match='bypass'):
        probe['inspect'](FONTS / 'NotoSerifHebrew-wdth-wght.ttf')
    monkeypatch.delenv('HOCRSYNGEN_EVAL_RENDER')
    with pytest.raises(ValueError, match='held-out'):
        probe['inspect'](Path('Simple CLM.ttf'))
    with pytest.raises(ValueError, match='excluded'):
        probe['inspect'](Path('Farissol.ttf'))
    with pytest.raises(ValueError, match='excluded'):
        probe['inspect'](FONTS / 'Cousine-Regular.ttf')


def test_composite_marks_are_checked(probe):
    _, report = probe['inspect'](FONTS / 'Tinos-Regular.ttf')
    cases = report['instances'][0]['cases']
    assert cases['dagesh-vowel']['issues'] == []
    marks = cases['dagesh-vowel']['marks']
    assert {m['mark']: m['component'] for m in marks} == {'U+05BC@1': True, 'U+05B8@1': False}
    assert cases['holam-male']['issues'] == []
    assert any(m['component'] and m['mark'] == 'U+05B9@3' for m in cases['holam-male']['marks'])


def test_arimo_stack_and_variable_weights(probe):
    _, report = probe['inspect'](FONTS / 'Arimo-wght.ttf', training_weights=True)
    assert [instance['weight'] for instance in report['instances']] == [400, 550, 700]
    for instance in report['instances']:
        assert instance['cases']['dagesh-vowel']['issues'] == []
        assert 'U+05B8@1 + U+0596@1: mark bboxes overlap' in instance['cases']['below-stack']['issues']


def test_missing_punctuation_and_hash_mismatch(probe):
    path = FONTS / 'OpenSans-wdth-wght.ttf'
    _, report = probe['inspect'](path)
    assert report['coverage']['sof_pasuq'] == 'no'
    assert report['coverage']['geresh'] == 'no'
    assert report['coverage']['gershayim'] == 'no'
    assert '.notdef' in report['instances'][0]['cases']['punctuation']['issues']
    with pytest.raises(ValueError, match='SHA-256'):
        probe['inspect'](path, expected_sha='0' * 64)


def test_v2_faces_render_through_the_governed_entry_point(tmp_path):
    from PIL import features
    from hocrsyngen.line_render import render_lines

    if not features.check_feature('raqm'):
        pytest.skip('needs Pillow with libraqm (see AGENTS.md)')
    text = 'גשָּׁ֖֨ג׃'
    summary = render_lines([{'id': 'probe-a', 'text': text}, {'id': 'probe-b', 'text': text}],
                           tmp_path / 'lines', seed=17, preset='none',
                           manifest_path=FONTS / 'manifest.niqqud-v2.yaml')
    assert not summary['refused']
    assert summary['by_font'] == {'cardo-regular': 1, 'ezra-sil-regular': 1}
