#!/usr/bin/env python3
"""Probe niqqud shaping on invented strings and make small RTL contact sheets."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from functools import lru_cache
from io import BytesIO
import json
import os
from pathlib import Path
import unicodedata

import uharfbuzz as hb
from fontTools.misc.transform import Identity
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont, features

from hocrsyngen.font_exclusion import EVAL_ENV, check_font
from hocrsyngen.line_render import governed_faces

ABOVE = {0x05B9, 0x05BA, 0x05BF, 0x05C1, 0x05C2, 0x05A8}
BELOW = set(range(0x05B0, 0x05B9)) | {0x05BB, 0x05BD, 0x05C7, 0x0596}
CORE = set(range(0x05B0, 0x05BD)) | {0x05C1, 0x05C2, 0x05C7}
ACCENTS = set(range(0x0591, 0x05B0))
LETTERS = set(range(0x05D0, 0x05EB))
# Culmus 0.140 renamed the held-out family's former bold italic to Farissol.
FORBIDDEN_NAMES = ('farissol', 'miriammono', 'cascadiacode', 'cascadiamono', 'cousine')
EXTRAS = {'meteg': 0x05BD, 'rafe': 0x05BF, 'sof_pasuq': 0x05C3,
          'geresh': 0x05F3, 'gershayim': 0x05F4}

# Use shin for its dots and vav for holam haser. A gimel on each side makes
# accidental attachment to either neighbor visible. None of the text is sourced.
CASES = {
    f'point-{cp:04X}': 'ג' + ('ש' if cp in (0x05C1, 0x05C2) else 'ו' if cp == 0x05BA else 'ב') + chr(cp) + 'ג'
    for cp in sorted(CORE | {0x05BD, 0x05BF})
}
CASES.update({
    'shin-dagesh': 'גשַּׁג', 'sin-dagesh': 'גשֶּׂג', 'shuruq': 'גבּוּג',
    'mappiq': 'גהַּג', 'dagesh-vowel': 'גבָּג', 'holam-male': 'גבּוֹג', 'holam-haser': 'גבּוֺג',
    'qamats-qatan': 'גבׇּג', 'narrow-qubuts': 'גדְוֻלַג', 'wide-qubuts': 'גדְשֻׁלַג',
    'qubuts-edge': 'בֻג', 'narrow-patah': 'גדְיָוַלַג', 'adjacent-holam': 'גדֹשׁוֹג',
    'meteg-stack': 'גדָֽג', 'above-stack': 'גבַּ֨ג', 'below-stack': 'גבָּ֖ג',
    'double-stack': 'גשָּׁ֖֨ג', 'punctuation': 'ג׳ ג״ב ג׃',
})

Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Glyph:
    gid: int
    cluster: int
    advance: int
    box: Box | None
    origin: tuple[int, int]


def shape(font: hb.Font, text: str) -> list[Glyph]:
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.direction = 'rtl'
    buffer.script = 'Hebr'
    buffer.language = 'he'
    hb.shape(font, buffer)
    x = y = 0
    glyphs = []
    for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
        ext = font.get_glyph_extents(info.codepoint)
        box = None
        if ext and ext.width and ext.height:
            left = x + pos.x_offset + ext.x_bearing
            top = y + pos.y_offset + ext.y_bearing
            box = (left, top + ext.height, left + ext.width, top)
        glyphs.append(Glyph(info.codepoint, info.cluster, pos.x_advance, box,
                            (x + pos.x_offset, y + pos.y_offset)))
        x += pos.x_advance
        y += pos.y_advance
    return glyphs


def overlaps(a: Box, b: Box, tolerance: float) -> bool:
    return (min(a[2], b[2]) - max(a[0], b[0]) > tolerance
            and min(a[3], b[3]) - max(a[1], b[1]) > tolerance)


def mark_geometry(cp: int, base_cp: int, mark: Box, base: Box, neighbors: list[Box], upem: int) -> list[str]:
    left, bottom, right, top = base
    x = (mark[0] + mark[2]) / 2
    y = (mark[1] + mark[3]) / 2
    tolerance = upem * 0.02
    messages = []
    if cp in ABOVE and y < top - tolerance:
        messages.append('above mark below top of base')
    if cp in BELOW and y > bottom + tolerance:
        messages.append('below mark above bottom of base')
    if base_cp == 0x05E9:
        base_center = (left + right) / 2
        if (cp == 0x05C1 and x < base_center - tolerance) or (cp == 0x05C2 and x > base_center + tolerance):
            messages.append('shin/sin dot on wrong side of base')
    if x < left - upem * 0.15 or x > right + upem * 0.15:
        messages.append('mark center outside base area')
    if cp == 0x05BC:
        # Shuruq belongs to the left of vav’s stroke. Dagesh/mappiq on
        # other letters normally sit within the base’s ink bounding box.
        min_x = left - (upem * 0.15 if base_cp == 0x05D5 else tolerance)
        if not (min_x <= x <= right + tolerance and bottom - tolerance <= y <= top + tolerance):
            messages.append('dagesh/mappiq position outside base area')
    if any(overlaps(mark, neighbor, tolerance) for neighbor in neighbors):
        messages.append('mark bbox overlaps neighboring letter')
    return messages


def component_reader(tt: TTFont, weight: float | None):
    """Expand TrueType composites, retaining each leaf and its transform."""
    glyph_set = tt.getGlyphSet(location={'wght': weight} if weight is not None else None)

    @lru_cache(maxsize=None)
    def leaves(name):
        pen = RecordingPen()
        try:
            glyph_set[name].draw(pen)
        except (AttributeError, NotImplementedError, RecursionError):
            return ()
        components = [args for op, args in pen.value if op == 'addComponent']
        if not components or 'glyf' not in tt:
            return ((name, Identity),)
        return tuple((leaf, Identity.transform(transform).transform(nested))
                     for component, transform in components for leaf, nested in leaves(component))

    return leaves


def composite_mark(font, marked, without, base_cp, tt, leaves):
    """Account for a point fused into an advancing TrueType glyph."""
    if not marked.advance:
        return None
    components = leaves(tt.getGlyphName(marked.gid))
    if len(components) < 2:
        return None
    control = Counter(name for glyph in without if glyph.advance
                      for name, _ in leaves(tt.getGlyphName(glyph.gid)))
    delta = Counter(name for name, _ in components) - control
    added = [(name, transform) for name, transform in components if delta[name]]
    nominal = font.get_nominal_glyph(base_cp)
    base_name = tt.getGlyphName(nominal) if nominal else None
    base = [(name, transform) for name, transform in components if name == base_name]
    if sum(delta.values()) != 1 or len(added) != 1 or len(base) != 1:
        return None

    def positioned(component):
        name, transform = component
        ext = font.get_glyph_extents(tt.getGlyphID(name))
        if not ext or not ext.width or not ext.height:
            return None
        bounds = (ext.x_bearing, ext.y_bearing + ext.height, ext.x_bearing + ext.width, ext.y_bearing)
        left, bottom, right, top = bounds
        xs, ys = zip(*transform.transformPoints([(left, bottom), (left, top), (right, bottom), (right, top)]))
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        x, y = marked.origin
        return x + x1, y + y1, x + x2, y + y2

    return positioned(added[0]), positioned(base[0])


def probe_case(font: hb.Font, text: str, cmap: set[int], dotted: int | None,
               upem: int, tt: TTFont, leaves) -> dict:
    text = unicodedata.normalize('NFC', text)
    glyphs = shape(font, text)
    issues = [f'missing U+{cp:04X}' for cp in sorted(set(map(ord, text)) - cmap)]
    if any(g.gid == 0 for g in glyphs):
        issues.append('.notdef')
    if dotted and any(g.gid == dotted for g in glyphs):
        issues.append('dotted circle')

    marks = []
    if issues:
        return {'text': text, 'issues': issues, 'marks': marks}
    base_index = 0
    for index, char in enumerate(text):
        if not unicodedata.combining(char):
            base_index = index
            continue
        cp = ord(char)
        if cp not in cmap or ord(text[base_index]) not in cmap:
            continue
        # Remove this input mark and compare glyph IDs in its own grapheme.
        # This can distinguish a separate substituted mark from a fused glyph.
        cluster = [g for g in glyphs if g.cluster == base_index]
        without = [g for g in shape(font, text[:index] + text[index + 1:]) if g.cluster == base_index]
        delta = Counter(g.gid for g in cluster) - Counter(g.gid for g in without)
        matching = [g for g in cluster if delta[g.gid]]
        # Some older fonts encode a combining point as an advancing glyph. It
        # still needs to be inspected, rather than mistaken for a second base.
        marked = matching[0] if sum(delta.values()) == len(matching) == 1 else None
        base = [g for g in cluster if g is not marked and g.advance and g.box]
        label = f'U+{cp:04X}@{base_index}'
        compound = composite_mark(font, marked, without, ord(text[base_index]), tt, leaves) if marked and not base else None
        if compound:
            mark_box, base_box = compound
        elif marked and len(base) == 1:
            mark_box, base_box = marked.box, base[0].box
        else:
            issues.append(f'{label}: mark identity or base inconclusive (possible substitution)')
            continue
        if not mark_box or not base_box:
            issues.append(f'{label}: mark or base has no visible extents')
            continue
        neighbors = [g.box for g in glyphs if g.cluster != base_index and g.advance and g.box]
        marks.append({'mark': label, 'glyph_id': marked.gid, 'box': mark_box,
                      'base_box': base_box, 'component': bool(compound)})
        if marked.advance and not compound:
            issues.append(f'{label}: combining glyph advances the pen')
        issues.extend(f'{label}: {message}' for message in mark_geometry(cp, ord(text[base_index]), mark_box, base_box, neighbors, upem))

    for i, mark in enumerate(marks):
        for other in marks[:i]:
            if overlaps(mark['box'], other['box'], upem * 0.02):
                issues.append(f"{other['mark']} + {mark['mark']}: mark bboxes overlap")
    return {'text': text, 'issues': issues, 'marks': marks}


def check_probe_name(name: str) -> None:
    check_font(name)
    normalized = ''.join(c for c in name.casefold() if c.isalnum())
    if any(alias in normalized for alias in FORBIDDEN_NAMES):
        raise ValueError(f'{name}: font alias excluded from pointed training')


def font_metadata(path: Path) -> tuple[bytes, dict, dict]:
    if os.environ.get(EVAL_ENV) == '1':
        raise ValueError('evaluation bypass is forbidden')
    check_font(path)
    check_probe_name(path.name)
    data = path.read_bytes()
    with TTFont(BytesIO(data)) as tt:
        for record in tt['name'].names:
            if record.nameID in (1, 4, 6, 16, 21):
                check_probe_name(record.toUnicode(errors='replace'))
        info = {'family': tt['name'].getBestFamilyName(), 'version': tt['name'].getDebugName(5),
                'monospace': bool(tt['post'].isFixedPitch or ('OS/2' in tt and tt['OS/2'].panose.bProportion == 9))}
        if info['monospace']:
            raise ValueError(f'{path.name}: monospace fonts are excluded from pointed training')
        axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in tt['fvar'].axes} if 'fvar' in tt else {}
    return data, info, axes


def verdict(cases: dict, coverage: dict) -> str:
    if coverage['hebrew_letters'] != 'full':
        return 'incomplete Hebrew alphabet'
    if coverage['core'] == 'none':
        return 'no core points'
    if coverage['core'] != 'full':
        return 'incomplete core coverage'
    issues = [issue for label, case in cases.items() if label not in
              {'point-05BD', 'point-05BF', 'meteg-stack', 'above-stack', 'below-stack', 'double-stack', 'punctuation'}
              for issue in case['issues']]
    if any('inconclusive' not in issue for issue in issues):
        return 'core placement or shaping flagged'
    if issues:
        return 'core substitution review'
    return 'core probe clear'


def inspect(path: Path, *, training_weights: bool = False, expected_sha: str | None = None) -> tuple[bytes, dict]:
    data, info, axes = font_metadata(path)
    sha = hashlib.sha256(data).hexdigest()
    if expected_sha and expected_sha != sha:
        raise ValueError(f'{path.name}: SHA-256 changed')
    face = hb.Face(data)
    font = hb.Font(face)
    font.scale = (face.upem, face.upem)
    cmap = set(face.unicodes)
    dotted = font.get_nominal_glyph(0x25CC)

    def visible(cp):
        gid = font.get_nominal_glyph(cp)
        extents = font.get_glyph_extents(gid) if gid else None
        return bool(extents and extents.width and extents.height)

    # Blank placeholders in some Culmus weights must not count as support.
    def coverage_of(codepoints):
        missing = sorted(cp for cp in codepoints if not visible(cp))
        return ('full' if not missing else 'none' if len(missing) == len(codepoints) else 'partial', missing)

    coverage = {label: 'yes' if visible(cp) else 'no' for label, cp in EXTRAS.items()}
    coverage['hebrew_letters'], _ = coverage_of(LETTERS)
    coverage['core'], missing_core = coverage_of(CORE)
    coverage['cantillation'], missing_accents = coverage_of(ACCENTS)
    weights = [None]
    if 'wght' in axes and training_weights:
        lo, _, hi = axes['wght']
        weights = sorted({max(lo, min(w, hi)) for w in (400, 550, 700)})
    instances = []
    for weight in weights:
        if weight is not None:
            font.set_variations({'wght': weight})
        with TTFont(BytesIO(data)) as tt:
            leaves = component_reader(tt, weight)
            cases = {label: probe_case(font, text, cmap, dotted, face.upem, tt, leaves) for label, text in CASES.items()}
            accents_unverified = [f'U+{cp:04X}' for cp in sorted(ACCENTS)
                                  if not probe_case(font, 'גב' + chr(cp) + 'ג', cmap, dotted,
                                                    face.upem, tt, leaves)['marks']]
        holams = []
        for label in ('holam-male', 'holam-haser'):
            found = [m for m in cases[label]['marks'] if m['mark'] in ('U+05B9@3', 'U+05BA@3')]
            if found:
                m = found[0]
                holams.append((sum(m['box'][::2]) - sum(m['base_box'][::2])) / 2)
        if len(holams) == 2 and holams[0] - holams[1] < face.upem * 0.02:
            cases['holam-haser']['issues'].append('vav holam pair has no clear right/left distinction')
        stacks = ('above-stack', 'below-stack', 'double-stack')
        stack_issues = [issue for label in stacks for issue in cases[label]['issues']]
        stack_probe = ('unsupported' if any(issue.startswith('missing ') for issue in stack_issues)
                       else 'flagged' if stack_issues else 'clear')
        instances.append({'weight': weight, 'verdict': verdict(cases, coverage),
                          'cantillation_unverified': accents_unverified,
                          'cantillation_stack_probe': stack_probe, 'cases': cases})
    return data, {'font': path.name, 'sha256': sha, 'harfbuzz': hb.version_string(), **info,
                  'axes': axes, 'units_per_em': face.upem, 'coverage': coverage,
                  'missing_core': [f'U+{cp:04X}' for cp in missing_core],
                  'missing_cantillation': [f'U+{cp:04X}' for cp in missing_accents], 'instances': instances}


def sheet(data: bytes, report: dict, output: Path) -> None:
    if not features.check_feature('raqm'):
        raise RuntimeError('Pillow needs libraqm for Hebrew contact sheets')
    instances = report['instances']
    rows = (len(CASES) + 1) // 2
    slot = 165
    cell = 115 + slot * len(instances)
    image = Image.new('RGB', (2 * cell, 58 + rows * 48), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((12, 9), f"{report['font']}   {report['sha256'][:16]}", fill='black')
    for column in range(2):
        offset = column * cell
        for j, instance in enumerate(instances):
            weight = instance['weight']
            label = f'{weight:g}' if weight is not None else 'default'
            draw.text((offset + 140 + slot * j, 31), str(label), fill='black')
    for j, instance in enumerate(instances):
        font = ImageFont.truetype(BytesIO(data), 38, layout_engine=ImageFont.Layout.RAQM)
        if instance['weight'] is not None:
            font.set_variation_by_axes([instance['weight'] if tag == 'wght' else default
                                        for tag, (_, default, _) in report['axes'].items()])
        for i, (label, case) in enumerate(instance['cases'].items()):
            column, row = divmod(i, rows)
            x = column * cell
            y = 63 + 48 * row
            if j == 0:
                draw.text((x + 10, y), label, fill='black')
            draw.text((x + 256 + slot * j, y + 18), case['text'], anchor='rs', font=font,
                      fill='black', direction='rtl', language='he')
            if case['issues']:
                draw.text((x + 260 + slot * j, y), '!', fill='darkred')
    image.save(output, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fonts', nargs='*', type=Path)
    parser.add_argument('--manifest', type=Path, help='verify and probe the exact faces in a governed manifest')
    parser.add_argument('--training-weights', action='store_true', help='probe 400, 550, 700, clipped to the wght axis')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if bool(args.fonts) == bool(args.manifest):
        parser.error('provide fonts or --manifest')
    if os.environ.get(EVAL_ENV) == '1':
        parser.error('evaluation bypass is forbidden')
    files = ([(f.id, f.path, f.sha256) for f in governed_faces(args.manifest).values()] if args.manifest
             else [(p.stem, p, None) for p in args.fonts])
    if len({name for name, *_ in files}) != len(files):
        parser.error('output names must be unique')
    args.output.mkdir(parents=True, exist_ok=True)
    for name, path, sha in files:
        data, report = inspect(path, training_weights=args.training_weights, expected_sha=sha)
        sheet(data, report, args.output / f'{name}.png')
        (args.output / f'{name}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
