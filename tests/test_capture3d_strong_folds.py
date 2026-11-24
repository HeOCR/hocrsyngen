import math
from dataclasses import asdict

import pytest

from experiments.capture3d.developable import DevelopablePaper, paper_model
from experiments.capture3d.geometry import distort
from experiments.capture3d.strong_folds import PROFILES, design


@pytest.mark.parametrize("profile", PROFILES)
def test_fold_mesh_preserves_paper_metric_and_covers_the_rectangle(profile):
    base = DevelopablePaper(.210, .297, 0, 0, ())
    sheet = paper_model(asdict(design(base, profile, 553916)))
    points, faces, uv = sheet.mesh()
    assert sheet.thickness == .0001
    assert min(point[2] for point in points) == pytest.approx(.001)
    assert max(point[2] for point in points) - min(point[2] for point in points) > .01

    area = 0.
    edges = {}
    for a, b, c in faces:
        (ua, va), (ub, vb), (uc, vc) = [uv[i] for i in (a, b, c)]
        triangle = ((ub - ua) * (vc - va) - (vb - va) * (uc - ua)) / 2
        assert triangle > 0
        area += triangle
        for i, j in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((i, j)))
            edges[key] = edges.get(key, 0) + 1
            rest = math.hypot((uv[i][0] - uv[j][0]) * sheet.width, (uv[i][1] - uv[j][1]) * sheet.height)
            assert math.dist(points[i], points[j]) / rest == pytest.approx(1., abs=8e-5)
    assert area == pytest.approx(1., abs=1e-9)
    for (a, b), repeats in edges.items():
        if repeats == 1:
            assert any(uv[a][i] == pytest.approx(border) and uv[b][i] == pytest.approx(border)
                       for border in (0, 1) for i in (0, 1))
        else:
            assert repeats == 2
    for xyz, (u, v) in zip(points, uv, strict=True):
        assert math.dist(xyz, sheet.at(u, 1 - v)) < 1e-10


@pytest.mark.parametrize("profile", ("quarter", "crossed", "crumple"))
def test_crossing_creases_are_in_polygon_and_rectification(profile):
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from experiments.capture3d.review import projection_map

    sheet = design(DevelopablePaper(.210, .297, 0, 0, ()), profile, 5)
    perimeter = sheet.perimeter((.08, .07, .93, .81))
    assert len(perimeter) >= 8
    for (u, v), (other_u, other_v) in zip(perimeter, (*perimeter[1:], perimeter[0]), strict=True):
        a, b = sheet.at(u, v), sheet.at(other_u, other_v)
        for fraction in (.2, .5, .8):
            interior = sheet.at(u + fraction * (other_u - u), v + fraction * (other_v - v))
            assert interior == pytest.approx(tuple(x + fraction * (y - x) for x, y in zip(a, b)), abs=1e-10)
    matrix = np.array([[4, 0, .1, -.03], [0, 4, .3, .05], [0, 0, .1, .2], [0, .2, -.9, 1]])
    sw, sh, width, height, k1 = 39, 61, 1200, 1600, .024
    mx, my = projection_map(sheet, matrix, (sw, sh), (width, height), k1)
    for x, y in ((0, 0), (18, 1), (12, 13), (7, 19), (38, 60)):
        a, b, _, w = matrix @ [*sheet.at((x + .5) / sw, (y + .5) / sh), 1]
        projected = distort((a / w + 1) * width / 2, (1 - b / w) * height / 2, width, height, k1)
        assert (mx[y, x], my[y, x]) == pytest.approx(tuple(value - .5 for value in projected), abs=.00008)


def test_strong_fold_is_opt_in_and_shared_by_the_twins():
    pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from experiments.capture3d.batch import assign_strong_folds

    cases = [{"pair_id": ident, "arm": arm} for ident in ("desk-01", "book-01") for arm in ("clean", "treated")]
    selected = assign_strong_folds(cases, ["book-01=dog-ear"], True, "manifest.json")
    assert selected[:2] == cases[:2]
    assert [row["strong_fold"] for row in selected[2:]] == ["dog-ear", "dog-ear"]
    assert all("strong_fold" not in row for row in cases)
    with pytest.raises(ValueError, match="require developable paper"):
        assign_strong_folds(cases, ["book-01=dog-ear"], False, "manifest.json")
    for assignments in (["book-01=trifold", "book-01=quarter"], ["bad=trifold"], ["desk-01=bad"]):
        with pytest.raises(ValueError, match="unique selected PAIR=PROFILE"):
            assign_strong_folds(cases, assignments, True, "manifest.json")
