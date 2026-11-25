from dataclasses import asdict
from math import dist

import pytest

from experiments.capture3d.developable import DevelopablePaper, paper_model
from experiments.capture3d.rounded_folds import RoundedCrossPaper, design
from experiments.capture3d.strong_folds import design as strong_design


FLAT = DevelopablePaper(.21, .29694, 0., 0., ())


@pytest.mark.parametrize(("profile", "count"), [
    ("diagonal", 1), ("half", 1), ("parallel", 2), ("three-parallel", 3), ("crossed", 2), ("dog-ear", 2),
])
def test_closed_crease_count_and_relative_edge_error(profile, count):
    paper = paper_model(asdict(design(FLAT, profile, 17)))
    sections = paper.sections if isinstance(paper, RoundedCrossPaper) else (paper,)
    assert paper.thickness == FLAT.thickness
    memory = [radius for section in sections for _, _, radius, crease in section.bends if crease]
    assert len(memory) == count
    assert all(.00025 <= radius <= .00046 for radius in memory)
    if profile != "dog-ear":
        assert all(any(radius > .1 for _, _, radius, crease in section.bends if not crease) for section in sections)
    xyz, faces, uv = paper.mesh()
    limit = .004 if profile == "crossed" else 8e-5
    for face in faces:
        assert len(set(face)) == 3
        for a, b in zip(face, (*face[1:], face[0]), strict=True):
            rest = dist((uv[a][0] * paper.width, uv[a][1] * paper.height),
                        (uv[b][0] * paper.width, uv[b][1] * paper.height))
            assert abs(dist(xyz[a], xyz[b]) / rest - 1) < limit


def test_dog_ear_replays_v4_exactly():
    assert design(FLAT, "dog-ear", 17) == strong_design(FLAT, "dog-ear", 17)


def test_crossing_rectification_and_perimeter_use_both_sections():
    pytest.importorskip("cv2")
    from experiments.capture3d.review import _rounded_cross_points

    paper = design(FLAT, "crossed", 17)
    pixels = _rounded_cross_points(paper, (29, 41))
    assert paper.crease_axes[0][0] == (1., 0.)
    assert paper.crease_axes[1][0] == (0., 1.)
    for i, j in [(0, 0), (13, 17), (28, 40)]:
        assert tuple(pixels[j, i]) == pytest.approx(paper.at((i + .5) / 29, (j + .5) / 41))
    boundary = paper.perimeter((.08, .07, .93, .81))
    assert len({u for u, v in boundary if v == .07}) > 4
    assert len({v for u, v in boundary if u == .93}) > 4
