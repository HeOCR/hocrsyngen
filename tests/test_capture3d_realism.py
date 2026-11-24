import pytest

from experiments.capture3d.geometry import Paper, distort
from experiments.capture3d.realism import FOLDS, LIGHT, PAPER, plan_realism

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")

from experiments.capture3d.batch import rejected_pairs
from experiments.capture3d.review import line_crop, projection_map


def test_scene_decks_vary_independently_and_controls_switch_off_only_the_camera():
    pages = [{"id": f"page-{i}", "scene": "desk", "seed": 811 + i} for i in range(24)]
    captures = list(plan_realism(pages, 553916))
    assert captures == list(plan_realism(pages, 553916))
    treated = [row["realism"] for row in captures[1::2]]
    assert {row["paper"]["stock"] for row in treated[:6]} == PAPER.keys()
    assert {row["lighting"]["profile"] for row in treated[:6]} == LIGHT.keys()
    assert {row["fold"]["profile"] for row in treated[:6]} == set(FOLDS)
    assert len({(row["paper"]["stock"], row["fold"]["profile"]) for row in treated}) > len(PAPER)
    for index in range(0, len(captures), 2):
        clean, treated = captures[index:index + 2]
        assert clean["seed"] == treated["seed"]
        assert clean["pair_id"] == treated["pair_id"]
        clean, treated = clean["realism"], treated["realism"]
        assert all(clean[field] == treated[field] for field in ("paper", "fold", "lighting"))
        assert all(not clean["camera"][key] for key in ("noise_strength", "flash_w", "motion_m", "fstop"))


def test_rectification_uses_the_actual_deformed_triangle_and_radial_camera():
    paper = Paper(dogear_size=.05, dogear_angle_deg=60, valley_depth=.018, divisions=(4, 6))
    matrix = np.array([[4, 0, .1, -.03], [0, 4, .3, .05], [0, 0, .1, .2], [0, .2, -.9, 1]])
    sx, sy, width, height, k1 = 19, 21, 1080, 1440, .024
    mx, my = projection_map(paper, matrix, (sx, sy), (width, height), k1)
    for x, y in ((0, 0), (18, 1), (12, 13), (7, 19)):
        uv = ((x + .5) / sx, (y + .5) / sy)
        a, b, _, w = matrix @ [*paper.at(*uv), 1]
        px, py = distort((a / w + 1) * width / 2, (1 - b / w) * height / 2, width, height, k1)
        assert (mx[y, x], my[y, x]) == pytest.approx((px - .5, py - .5), abs=7e-5)
    assert line_crop(np.zeros((100, 100)), (27.1, 25.2, 53.4, 64.4)).shape == (64, 61)


def test_pairs_reject_hidden_text_and_changed_polygons():
    shared = {"pair_id": "desk-01", "scene": "desk", "paper": {}, "clip_from_sheet": [],
              "phone": {"k1": .02}, "annotations": [{"polygon": [[20, 30]]}], "rejected_regions": []}
    clean, treated = {**shared, "arm": "clean"}, {**shared, "arm": "treated"}
    assert not rejected_pairs([clean, treated])
    assert rejected_pairs([clean, {**treated, "rejected_regions": ["l1"]}]) == {"desk-01"}
    with pytest.raises(ValueError, match="Twin geometry changed"):
        rejected_pairs([clean, {**treated, "annotations": [{"polygon": [[20, 31]]}]}])
