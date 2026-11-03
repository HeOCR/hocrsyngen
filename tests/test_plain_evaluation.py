from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from hocrsyngen import generator
from hocrsyngen.generator import _LineRecorder, generate_batch
from hocrsyngen.validation import validate_batch


def test_plain_preset_is_explicit_and_paired(tmp_path: Path) -> None:
    ordinary = generate_batch(1, 33, tmp_path / 'ordinary', emit_line_annotations=True)
    plain = generate_batch(1, 33, tmp_path / 'plain', emit_line_annotations=True,
                           emit_paired_render=True, plain_evaluation=True)
    assert 'composition_mode' not in ordinary.to_dict()['samples'][0]['provenance']
    assert plain.to_dict()['samples'][0]['provenance']['composition_mode'] == 'plain_evaluation'
    assert (tmp_path / 'plain' / 'paired_render.json').exists()
    validate_batch(tmp_path / 'plain')
    assert ordinary.samples[0].text.logical_order == plain.samples[0].text.logical_order
    assert ordinary.samples[0].pages[0].sha256 != plain.samples[0].pages[0].sha256


def test_plain_recorder_rejects_main_flow_overlap_and_clip() -> None:
    image = Image.new('RGB', (200, 100), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(Path(generator.__file__).parent / 'data/synthetic/fonts/Alef-Regular.ttf'), 20)
    rec = _LineRecorder(plain_evaluation=True)
    for x, y, text in [(100, 10, 'one'), (100, 10, 'two'), (0, 50, 'out')]:
        rec.record(draw, (x, y), text, font=font, anchor='ra', region='body',
                   logical_line_index=0, logical_join=None)
    lines = rec.final_lines(image.size)
    assert all(line.occluded for line in lines)
    assert lines[-1].clipped


def test_plain_rejects_text_clipped_before_rotation_even_when_rotated_inside() -> None:
    from hocrsyngen.generator import _RecordedLine

    rec = _LineRecorder(plain_evaluation=True, rotation_degrees=-10)
    rec.lines.append(_RecordedLine('body', 'x', 0, None, (0, 24, 17, 26), 28, 'body'))
    line = rec.final_lines((200, 100))[0]
    assert line.clipped and line.occluded
