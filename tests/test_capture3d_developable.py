import math
import json
from hashlib import sha256

import pytest

from experiments.capture3d.developable import DevelopablePaper, from_capture, paper_model
from experiments.capture3d.geometry import Paper, distort


@pytest.mark.parametrize("profile", ("light curl", "deep crease", "double fold", "crumple", "dog-ear", "crumple and dog-ear"))
def test_straight_fold_bands_preserve_the_cut_sheet(profile):
    design = from_capture(Paper(dogear_corner=(-1, 1), dogear_size=.043), "letter", {"fold": {"profile": profile}}, 625011)
    points, triangles, uv = design.mesh()
    assert len(points) == len(set(uv)) and len(triangles) > 2
    assert design.thickness == .0001
    assert all(.0002 <= radius <= .0005 for _, _, radius, crease in design.bends if crease)
    for face in triangles:
        assert len(set(face)) == 3
        for a, b in zip(face, (face[1], face[2], face[0]), strict=True):
            distance = math.hypot((uv[a][0] - uv[b][0]) * design.width, (uv[a][1] - uv[b][1]) * design.height)
            assert math.dist(points[a], points[b]) / distance == pytest.approx(1., abs=8e-5)
    for xyz, (u, v) in zip(points, uv, strict=True):
        assert math.dist(xyz, design.at(u, 1 - v)) < 1e-10


def test_book_spine_flattens_on_a_constant_radius():
    design = from_capture(Paper(), "book", {"fold": {"profile": "double fold"}}, 1, facing=True)
    assert len(design.bends) == 1
    start = design.at(0, .5)
    assert start[2] > .01
    assert design.at(.5, .5)[2] == pytest.approx(design.at(.95, .5)[2])
    assert design.normal(.5, .5) == pytest.approx((0, 0, 1))


def test_developable_rectification_uses_matching_strip_not_a_resampled_grid():
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from experiments.capture3d.review import projection_map

    record = dict(width=.21, height=.297, axis_deg=138., initial_deg=-12.,
                  bends=[(.009, 34., .00032, True)], model="developable")
    paper = paper_model(record)
    assert isinstance(paper, DevelopablePaper)
    assert isinstance(paper_model({}), Paper)
    edge = paper.perimeter((.18, .2, .9, .83))
    assert len(edge) > 10 and len(edge) == len(set(edge))
    matrix = np.array([[4, 0, .1, -.03], [0, 4, .3, .05], [0, 0, .1, .2], [0, .2, -.9, 1]])
    sw, sh, width, height, k1 = 39, 61, 1200, 1600, .024
    mx, my = projection_map(paper, matrix, (sw, sh), (width, height), k1)
    for x, y in ((0, 0), (18, 1), (12, 13), (7, 19), (38, 60)):
        a, b, _, w = matrix @ [*paper.at((x + .5) / sw, (y + .5) / sh), 1]
        projected = distort((a / w + 1) * width / 2, (1 - b / w) * height / 2, width, height, k1)
        assert (mx[y, x], my[y, x]) == pytest.approx(tuple(value - .5 for value in projected), abs=.00008)


def test_frozen_v2_individual_focus_survives_preset_replay(tmp_path):
    pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from experiments.capture3d.batch import frozen_cases

    source = tmp_path / "pages.json"
    source.write_text("{}")
    profiles = {"camera": {"fstop": 2.61, "focus_offset_m": .048}}
    pair = [{"id": f"desk-01-{arm}", "pair_id": "desk-01", "arm": arm, "scene": "desk", "seed": 553916,
             "font_sha256": "font", "source_sha256": "paper", "realism": profiles, "phone": {"fstop": 2.61}}
            for arm in ("clean", "treated")]
    frozen = tmp_path / "v2.json"
    frozen.write_text(json.dumps({"schema": "heocr.capture3d.paired.v2", "source_manifest_sha256": sha256(source.read_bytes()).hexdigest(),
                                  "realism_seed": 553916, "image_size": [1200, 1600], "cycles_samples": 16,
                                  "scene_assets": {}, "selected_pairs": [pair]}))
    regenerated = [{**row, "sha256": "paper", "realism": {"camera": {"fstop": 3.22}}} for row in pair]
    replay = list(frozen_cases(regenerated, frozen, source, {}, 553916, [1200, 1600], 16, ["desk-01"]))
    assert len(replay) == 2
    assert replay[1]["realism"] == profiles
    assert replay[1]["frozen_phone"] == pair[1]["phone"]
    with pytest.raises(ValueError, match="outside the frozen v2 roster"):
        list(frozen_cases(regenerated, frozen, source, {}, 553916, [1200, 1600], 16, ["desk-02"]))
