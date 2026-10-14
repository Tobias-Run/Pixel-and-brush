"""Offline-Katalogadapter. Live-CDSE bewusst erst in Phase 2 (siehe docs/CDSE.md)."""

from pathlib import Path
from typing import Protocol
from datetime import date

from pydantic import Field
from archaeo.config import Config, StrictModel
from archaeo.errors import PipelineError


class Scene(StrictModel):
    id: str
    date: date
    red: Path
    nir: Path
    scl: Path
    bbox: tuple[float, float, float, float]
    source_urls: list[str] = Field(default_factory=list)
    band_resolution_m: dict[str, float] = Field(
        default_factory=lambda: {"B04": 10.0, "B08": 10.0, "SCL": 20.0}
    )


class Catalog(Protocol):
    def search(self, config: Config) -> list[Scene]: ...


class FixtureCatalog:
    def __init__(self, scenes: list[Scene]) -> None:
        self.scenes = scenes

    def search(self, config: Config) -> list[Scene]:
        from shapely.geometry import box

        aoi = config.aoi.geometry()
        return [
            s
            for s in self.scenes
            if config.start <= s.date <= config.end and box(*s.bbox).intersects(aoi)
        ][: config.limits.max_scenes]


def search(config: Config, catalog: Catalog | None = None) -> list[Scene]:
    if catalog is None:
        raise PipelineError("Live-CDSE ist Phase 2; nutze --catalog mit lokalem Szenenmanifest")
    scenes = catalog.search(config)
    if not scenes:
        raise PipelineError("Keine Katalogtreffer für AOI/Zeitraum")
    return scenes[: config.limits.max_scenes]


def read_scenes(path: Path) -> list[Scene]:
    import json

    scenes = [Scene.model_validate(v) for v in json.loads(path.read_text())]
    for scene in scenes:
        for band in ("red", "nir", "scl"):
            setattr(scene, band, path.resolve().parent / getattr(scene, band))
    return scenes
