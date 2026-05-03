from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal
import unicodedata


GENERATION_MANIFEST_VERSION = "1.0"
PROJECT_SYNTHETIC_LICENSE = "PROJECT-SYNTHETIC"
SYNTHETIC_DISCLOSURE = (
    "Generated synthetic Hebrew OCR/HTR sample. It is candidate synthetic input for "
    "hocrgen governance and is not real-source provenance."
)


@dataclass(frozen=True)
class TextMetadata:
    logical_order: str
    script: Literal["Hebr"] = "Hebr"
    language: Literal["he"] = "he"
    direction: Literal["rtl"] = "rtl"
    unicode_normalization: Literal["NFC"] = "NFC"

    def __post_init__(self) -> None:
        if self.logical_order != unicodedata.normalize("NFC", self.logical_order):
            raise ValueError("Manifest logical_order text must be NFC-normalized.")


@dataclass(frozen=True)
class PageAsset:
    page_id: str
    asset_path: str
    media_type: Literal["image/jpeg"]
    sha256: str
    width: int
    height: int

    def __post_init__(self) -> None:
        path = PurePosixPath(self.asset_path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.asset_path:
            raise ValueError(f"Manifest asset paths must be relative portable paths: {self.asset_path}")


@dataclass(frozen=True)
class SampleProvenance:
    seed: int
    sample_index: int
    template_id: str
    recipe_id: str
    degradation_preset: str
    font_id: str
    source_corpus: str


@dataclass(frozen=True)
class SampleControls:
    persona: str | None = None
    condition: str | None = None


@dataclass(frozen=True)
class GeneratedSample:
    sample_id: str
    pages: list[PageAsset]
    text: TextMetadata
    generator_version: str
    recipe_id: str
    provenance: SampleProvenance
    license: Literal["PROJECT-SYNTHETIC"] = PROJECT_SYNTHETIC_LICENSE
    synthetic_disclosure: str = SYNTHETIC_DISCLOSURE
    controls: SampleControls = field(default_factory=SampleControls)


@dataclass(frozen=True)
class GenerationManifest:
    samples: list[GeneratedSample]
    generator_name: Literal["hocrsyngen"] = "hocrsyngen"
    manifest_version: Literal["1.0"] = GENERATION_MANIFEST_VERSION
    license: Literal["PROJECT-SYNTHETIC"] = PROJECT_SYNTHETIC_LICENSE
    synthetic_disclosure: str = SYNTHETIC_DISCLOSURE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
