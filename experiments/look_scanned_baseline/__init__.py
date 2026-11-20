"""Global raster effects adapted from Look Scanned under the MIT licence."""

from dataclasses import dataclass, fields
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_WHITE = (255, 255, 255)
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
_SEPIA = np.array(
    [[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]],
    dtype=np.float32,
)


@dataclass(frozen=True)
class ScanEffects:
    blur_px: float = 0.0
    border: bool = False
    brightness: float = 1.0
    colorspace: str = "sRGB"
    contrast: float = 1.0
    noise_stddev: float = 0.0
    rotate_deg: float = 0.0
    rotate_variance_deg: float = 0.0
    scale: float = 1.0
    yellowish: float = 0.0

    def __post_init__(self):
        if type(self.border) is not bool or self.colorspace not in ("gray", "sRGB"):
            raise ValueError("Select a boolean border and colorspace gray or sRGB")
        for field in fields(self):
            if field.name in ("border", "colorspace"):
                continue
            value = getattr(self, field.name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{field.name} must be a finite number")
            if field.name != "rotate_deg" and value < 0:
                raise ValueError(f"{field.name} must be non-negative")
        if not 0 < self.scale <= 3:
            raise ValueError("scale must be greater than 0 and at most 3")
        if self.yellowish > 1 or self.noise_stddev > 1:
            raise ValueError("yellowish and noise_stddev must be at most 1")


@dataclass(frozen=True)
class ScannedPage:
    image: Image.Image
    source_size: tuple[int, int]
    rotation_deg: float

    def transform_points(self, points):
        """Map points in source pixel-edge coordinates into the output page."""
        width, height = self.image.size
        source_width, source_height = self.source_size
        relative = (np.asarray(points) * [width / source_width, height / source_height]
                    - [width / 2, height / 2])
        angle = math.radians(self.rotation_deg)
        cosine, sine = math.cos(angle), math.sin(angle)
        clockwise = np.array([[cosine, sine], [-sine, cosine]])
        return relative @ clockwise + [width / 2, height / 2]


def _tone(image, effects):
    pixels = np.asarray(image, dtype=np.float32) / 255
    if effects.colorspace == "gray":
        pixels = (pixels @ _LUMA)[..., None].repeat(3, axis=2)
    pixels = np.clip(pixels * effects.brightness, 0, 1)
    if effects.yellowish:
        pixels = np.clip(
            (1 - effects.yellowish) * pixels + effects.yellowish * (pixels @ _SEPIA.T),
            0, 1,
        )
    pixels = np.clip((pixels - 0.5) * effects.contrast + 0.5, 0, 1)
    return Image.fromarray(np.rint(pixels * 255).astype(np.uint8))


def apply_scan_effects(source: Image.Image, effects: ScanEffects, *, seed: int) -> ScannedPage:
    """Apply seeded flat scan effects to one raster and retain its point transform."""
    rotation_rng, noise_rng = (np.random.default_rng(stream)
                               for stream in np.random.SeedSequence(seed).spawn(2))
    rotation = effects.rotate_deg + effects.rotate_variance_deg * rotation_rng.random()
    rgba = source.convert("RGBA")
    page = Image.new("RGB", source.size, _WHITE)
    page.paste(rgba, mask=rgba.getchannel("A"))
    size = tuple(max(1, round(dim * effects.scale)) for dim in source.size)
    if size != source.size:
        page = page.resize(size, Image.Resampling.LANCZOS)
    if effects.blur_px:
        page = page.filter(ImageFilter.GaussianBlur(effects.blur_px))
    page = _tone(page, effects)
    if rotation:
        page = page.rotate(-rotation, Image.Resampling.BICUBIC, fillcolor=_WHITE)
    if effects.noise_stddev:
        noise = noise_rng.normal(0, effects.noise_stddev * 255, (page.height, page.width, 1))
        pixels = np.clip(np.asarray(page) + noise, 0, 255)
        page = Image.fromarray(np.rint(pixels).astype(np.uint8))
    if effects.border:
        ImageDraw.Draw(page).rectangle((0, 0, page.width - 1, page.height - 1), outline="black")
    return ScannedPage(page, source.size, rotation)
