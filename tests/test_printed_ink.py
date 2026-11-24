import pytest

from hocrsyngen.printed_ink import extract_ink, multiply_ink, soft_ink_edge

np = pytest.importorskip("numpy")
ndimage = pytest.importorskip("scipy.ndimage")


def test_local_gray_paper_and_its_patch_edge_never_reach_target_paper():
    gray = np.broadcast_to(np.linspace(157, 220, 35, dtype=np.float32), (31, 35)).copy()
    gray[5:26, 5:30] -= 11
    gray[8:23, 15:20] -= 33
    gray[9:22, 16:19] = 29
    gray[10:22, 25] = 41  # A neighbouring stroke belongs to a different glyph.
    anchor = np.zeros_like(gray, dtype=bool)
    anchor[9:22, 16:19] = True
    opacity = extract_ink(gray, anchor)
    assert opacity[15, 17] == pytest.approx(1)
    assert 0 < opacity[15, 15] < 0.5
    assert not opacity[:, :14].any()
    assert not opacity[:, 21:].any()
    paper = np.full_like(gray, 180)
    target = multiply_ink(paper, opacity, ink_transmission=0.3)
    assert (target[opacity == 0] == 180).all()
    assert target[15, 17] == 54


def test_final_soft_edge_leaves_solid_ink_and_drops_warp_residue():
    opacity = np.full((15, 15), 0.10, dtype=np.float32)
    opacity[5:10, 5:10] = 0.9
    clean = soft_ink_edge(opacity)
    assert clean[7, 7] == opacity[7, 7]
    assert 0 < clean[5, 4] <= opacity[5, 4]
    assert clean[5, 3] == 0
