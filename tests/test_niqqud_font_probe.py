"""Small safety and geometry smoke checks for the optional font probe."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip('uharfbuzz')
pytest.importorskip('fontTools')

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/niqqud/check_fonts.py'
spec = importlib.util.spec_from_file_location('niqqud_font_probe', SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
FONT = Path(__file__).resolve().parents[1] / 'src/hocrsyngen/data/synthetic/fonts/NotoSerifHebrew-wdth-wght.ttf'


def test_held_out_filenames_rejected_even_under_bypass(monkeypatch):
    monkeypatch.setenv('HOCRSYNGEN_EVAL_RENDER', '1')
    with pytest.raises(ValueError, match='forbidden'):
        probe.inspect(FONT)
    monkeypatch.delenv('HOCRSYNGEN_EVAL_RENDER')
    with pytest.raises(ValueError, match='held-out'):
        probe.inspect(Path('Simple CLM.ttf'))


def test_known_font_and_combination_uncertainty():
    result = probe.inspect(FONT)
    assert result['sha256'] == '93caef921360788dc3b0e32136bb26f16bc57717ec482d48fc7fd43820617165'
    cases = {c['case']: c for c in result['cases']}
    assert cases['point-05B0']['issues'] == []
    assert 'geometry and mark identity not checked for combinations' in cases['above-stack']['issues']
