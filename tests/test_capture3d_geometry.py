import math

import pytest

from experiments.capture3d.geometry import Paper, distort, undistort


def test_uv_boundaries_include_the_actual_triangle_crossings():
    paper = Paper(curl=.018, crease_height=.012, crumple=.002, divisions=(4, 6))
    vertices, faces, uv = paper.mesh()
    assert len(vertices) == len(uv) == 35
    assert len(faces) == 48
    first = faces[0]
    want = tuple(sum(vertices[i][axis] for i in first) / 3 for axis in range(3))
    assert paper.at(1 / 12, 1 / 9) == pytest.approx(want)
    edge = paper.perimeter((.09, .10, .93, .88))
    assert (.15, .10) == pytest.approx(edge[1])  # First cell diagonal crosses the top UV edge.
    assert len(edge) == len(set(edge))
    assert edge[0] == (.09, .10)


@pytest.mark.parametrize("k1", [-.06, 0, .029])
def test_radial_ground_truth_uses_the_same_inverse_as_photo_resampling(k1):
    for point in ((.5, .5), (719.5, .5), (582.5, 768.5), (360, 480)):
        distorted = distort(*point, 720, 960, k1)
        recovered = undistort(*distorted, 720, 960, k1)
        assert math.dist(recovered, point) < 1e-8


def test_fold_valley_and_dogear_are_part_of_the_projected_mesh():
    paper = Paper(valley_depth=.036, valley_v=.64, dogear_size=.048,
                  dogear_angle_deg=58, dogear_corner=(1, 1), divisions=(64, 88))
    valley = paper.shape(.5, .64)
    assert paper.shape(.5, .60)[2] - valley[2] > .019
    assert paper.shape(.5, .68)[2] - valley[2] > .019
    tip = paper.shape(1, 0)
    assert tip[0] < paper.width / 2
    assert tip[1] < paper.height / 2
    assert tip[2] - .0015 == pytest.approx(.048 / math.sqrt(2) * math.sin(math.radians(58)))
    assert paper.at(1, 0) == pytest.approx(tip)
