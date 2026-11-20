"""Archive detail text must stay inside its own column."""
from __future__ import annotations

from pathlib import Path
from random import Random
from unittest.mock import patch

import pytest
from PIL import ImageDraw

from hocrsyngen import generator


def _font() -> Path:
    return Path(generator.__file__).parent / 'data/synthetic/fonts/Alef-Regular.ttf'


def _render(seed, body, style='style_standard_v1', template='archive_card', recorder=None):
    return generator._draw_archive_card(
        Random(seed), 'כותרת', body, 'סוף', _font(), template,
        generator.STYLE_BUNDLES[style], generator.CONDITION_BUNDLES['condition_standard_v1'], recorder,
    )


def test_archive_rejects_unbreakable_token_wider_than_body():
    # At seed 17 the old renderer put this body across the label column while
    # reporting neither page clipping nor occlusion.
    with pytest.raises(ValueError, match='wider than the body'):
        _render(17, ['א' * 32], recorder=generator._LineRecorder())


@pytest.mark.parametrize('seed', [3, 17, 41])
@pytest.mark.parametrize('style', list(generator.STYLE_BUNDLES))
@pytest.mark.parametrize('template', ['archive_card', 'archive_card_faded_scan'])
def test_archive_mixed_wrapped_lines_remain_right_of_separator(seed, style, template):
    calls = []
    original = ImageDraw.ImageDraw.line

    def capture(draw, xy, *args, **kwargs):
        if isinstance(xy, tuple) and len(xy) == 4 and xy[0] == xy[2] and xy[3] - xy[1] > 500:
            calls.append(xy)
        return original(draw, xy, *args, **kwargs)

    recorder = generator._LineRecorder()
    with patch.object(ImageDraw.ImageDraw, 'line', capture):
        _render(seed, ['אבג example 123 שלום עולם ' * 8], style, template, recorder)
    # The archive card has exactly one vertical separator spanning its body.
    assert len(calls) == 1
    separator = calls[0][0]
    body = [line for line in recorder.lines if line.region == 'body']
    assert len(body) > 1
    assert all(line.box[0] - generator.LINE_POLYGON_PADDING > separator for line in body)


def test_valid_archive_pixels_and_labels_match_pre_guard_render():
    body = ['שלום example 123 עולם שלום', 'מסמך מספר 42']
    before_recorder = generator._LineRecorder()
    with patch.object(generator, '_require_segment_fits'):
        before = _render(17, body, recorder=before_recorder)
    after_recorder = generator._LineRecorder()
    after = _render(17, body, recorder=after_recorder)
    assert before.image.tobytes() == after.image.tobytes()
    assert before.logical_lines == after.logical_lines
    assert before_recorder.final_lines(generator.CANVAS_SIZE) == after_recorder.final_lines(generator.CANVAS_SIZE)


@pytest.mark.parametrize('template', ['archive_card', 'archive_card_faded_scan'])
@pytest.mark.parametrize('seed', [3, 17, 41])
def test_bundled_default_corpus_pages_remain_byte_identical(template, seed):
    corpus = generator.load_text_corpus(
        Path(generator.__file__).parent / 'data/synthetic/texts/hebrew_lines.txt'
    )[:4]
    with patch.object(generator, '_require_segment_fits'):
        previous = _render(seed, corpus, template=template)
    current = _render(seed, corpus, template=template)
    assert current.image.tobytes() == previous.image.tobytes()
    assert current.logical_lines == previous.logical_lines
