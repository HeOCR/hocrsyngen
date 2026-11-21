"""Source-matched archival probes for DEV visual comparisons."""

from itertools import groupby
import random

from hocrsyngen.print_typography import render_print_page

from .degradations import show_through, soft_scanner_edge
from .dev_profiles import apply_profile
from .pipeline import _rng


SOURCES = {"green_book": "book", "stuart_book": "book", "gazette_archive": "gazette"}


def _paragraphs(page):
    return {" ".join(line["text"] for line in lines)
            for _, lines in groupby(page.lines, key=lambda line: line["paragraph"])}


def render_verso(front, paragraphs, *, seed, source_type, body_px=32):
    """Lay out a distinct reverse in normal reading orientation before mirroring."""
    if source_type not in SOURCES or type(seed) is not int or seed < 0:
        raise ValueError("expected an archival source type and nonnegative seed")
    paragraphs = tuple(paragraphs)
    if _paragraphs(front).intersection(p.text for p in paragraphs):
        raise ValueError("reverse paragraphs and titles must be distinct from the recto")
    layout = random.Random(f"archival-verso:{seed}")
    width, height = front.image.size
    # Offset the reverse's text block down the leaf, including its heading.
    side = round(width * layout.uniform(0.085, 0.125))
    top = front.lines[0]["box"][1] + round(height * layout.uniform(0.03, 0.055))
    return render_print_page(paragraphs, seed=layout.getrandbits(64),
                             source_type=SOURCES[source_type], size=(width, height),
                             body_px=body_px, margin=(side, top))


def archival_dev_view(front, *, source_type, fits, seed, reverse=None, edge=None):
    """Apply one full source fit for tone, optics and spatial noise.

    The fit bank maps a source type to its base and optional conditional duplex
    fit. Supply a separately rendered verso and/or an explicitly enabled soft
    edge to compare the overlays on the same front. The fitted base is shared
    across these ablations. This entry point stays outside training recipes.
    """
    if source_type not in SOURCES or type(seed) is not int or seed < 0:
        raise ValueError("expected an archival source type and nonnegative seed")
    fits_for_source = fits[source_type]
    base = fits_for_source["base"]
    if base.get("name") != "flatbed_old" or base.get("status") != "dev_fit":
        raise ValueError("archival tone and noise require a fitted flatbed profile")
    old_overlays = ("show_through_opacity", "scanner_edge_fraction",
                    "scanner_bar_fraction", "scanner_bars")
    if any(any(base["ranges"][key]) for key in old_overlays):
        raise ValueError("use a base fit with its legacy raster overlays disabled")

    page = front.image
    if reverse is not None:
        if reverse.image.size != page.size or _paragraphs(front) & _paragraphs(reverse):
            raise ValueError("use an independent verso with the same page dimensions")
        duplex = fits_for_source.get("duplex", {})
        if duplex.get("status") != "conditional_dev_fit":
            raise ValueError("show-through requires a matched source duplex fit")
        ranges = duplex["ranges"]
        blur = tuple(v * max(page.size) for v in ranges["blur_fraction_long_edge"])
        transmission_seed = int(_rng(seed, "archival_dev/verso").bit_generator.random_raw())
        page = show_through(page, reverse.image, transmission_seed, opacity=ranges["opacity"],
                            blur_px=blur, offset_fraction=ranges["offset_fraction"],
                            transmission_variation=0.25)
    result = apply_profile(page, base, seed=seed)
    if edge is not None:
        text_box = tuple(fn(line["box"][coordinate] for line in front.lines)
                         for coordinate, fn in enumerate((min, min, max, max)))
        result = soft_scanner_edge(result, seed, text_box=text_box, **edge)
    return result
