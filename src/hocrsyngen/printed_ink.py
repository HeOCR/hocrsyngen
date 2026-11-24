"""Extract antialiased printing ink independently of the paper in a source crop."""

from __future__ import annotations

from math import sqrt


def soft_ink_edge(opacity, core=None):
    """Keep the ink and its immediate one-pixel antialias band."""
    import numpy as np
    from scipy import ndimage

    alpha = np.asarray(opacity, dtype=np.float32)
    if core is None:
        core = alpha >= .47
    if not core.any():
        return np.zeros_like(alpha)
    distance = ndimage.distance_transform_edt(~core)
    # Include the diagonal neighbours with less coverage than a shared side.
    support = np.clip(2 - distance, 0, 1) * (distance <= sqrt(2))
    position = np.clip((alpha - .055) / .115, 0, 1)
    return (alpha * support * position ** 2 * (3 - 2 * position)).astype(np.float32)


def extract_ink(gray, anchor):
    """Normalise local source paper to white and return only the owned ink opacity."""
    import numpy as np
    from scipy import ndimage

    gray = np.asarray(gray, dtype=np.float32)
    anchor = np.asarray(anchor, dtype=bool)
    if gray.ndim != 2 or gray.shape != anchor.shape or not anchor.any() or anchor.all():
        raise ValueError("Expected a gray glyph crop with ink and surrounding paper")
    paper_level = float(np.percentile(gray[~anchor], 82))
    black = float(np.percentile(gray[anchor], 14))
    if paper_level - black < 26:
        raise ValueError("The native gray glyph has too little contrast")
    paper = ndimage.gaussian_filter(ndimage.grey_closing(gray, size=(9, 9)), 1.3)
    paper = np.clip(paper, max(black + 26, paper_level - 16), paper_level + 12)
    normalised_white = (gray - black) / (paper - black)
    alpha = np.clip(1 - normalised_white, 0, 1)
    heavy = (alpha >= .47) & ndimage.binary_dilation(anchor, iterations=2)
    owned = ndimage.binary_propagation(heavy & anchor, mask=heavy, structure=np.ones((3, 3)))
    if not owned.any():
        raise ValueError("The source glyph has no owned ink")
    return soft_ink_edge(alpha, owned)


def multiply_ink(paper, alpha, *, ink_transmission):
    """Multiply ink transmission onto the destination paper without patch pixels."""
    import numpy as np

    return np.rint(np.clip(paper * (1 - (1 - ink_transmission) * alpha), 0, 255)).astype(np.uint8)
