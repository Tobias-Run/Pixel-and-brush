from datetime import date
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pyproj import CRS
from shapely.geometry import box, shape
import json


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AOI(StrictModel):
    bbox: tuple[float, float, float, float] | None = None
    geojson: Path | None = None

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (self.bbox is None) == (self.geojson is None):
            raise ValueError("Genau eine AOI: bbox oder geojson")
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if not (-180 <= x0 < x1 <= 180 and -90 <= y0 < y1 <= 90):
                raise ValueError("Leere/ungültige WGS84-BBox")
        return self

    def geometry(self) -> object:
        if self.bbox is not None:
            return box(*self.bbox)
        assert self.geojson is not None
        raw = json.loads(self.geojson.read_text())
        if raw.get("type") == "Feature":
            raw = raw["geometry"]
        geom = shape(raw)
        if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("AOI muss gültiges, nicht leeres Polygon sein")
        if not box(-180, -90, 180, 90).covers(geom):
            raise ValueError("AOI muss WGS84-Koordinaten enthalten")
        return geom


class Grid(StrictModel):
    crs: str = "EPSG:32632"
    resolution: float = Field(default=10, gt=0)
    window_size: int = Field(default=128, ge=16, le=1024)

    @model_validator(mode="after")
    def valid(self) -> Self:
        crs = CRS.from_user_input(self.crs)
        if not crs.is_projected or any(a.unit_name != "metre" for a in crs.axis_info):
            raise ValueError("Ziel-CRS muss projiziert mit Metern sein")
        return self


class Parameters(StrictModel):
    threshold: float = Field(default=0.08, gt=0, le=2)
    min_observations: int = Field(default=3, ge=1)
    min_pixels: int = Field(default=2, ge=1)
    context_radius: int = Field(default=3, ge=1, le=32)


class Limits(StrictModel):
    max_scenes: int = Field(default=12, ge=1, le=100)
    max_pixels: int = Field(default=10000000, ge=1)
    max_download_bytes: int = Field(default=1000000000, ge=1)


class Paths(StrictModel):
    cache: Path = Path("data/cache")
    scenes: Path = Path("data/scenes.json")
    output: Path = Path("exports/run")
    register_file: Path | None = Field(default=None, alias="register")
    landuse: Path | None = None
    historical_map: Path | None = None


class Config(StrictModel):
    aoi: AOI
    start: date
    end: date
    grid: Grid = Field(default_factory=Grid)
    parameters: Parameters = Field(default_factory=Parameters)
    limits: Limits = Field(default_factory=Limits)
    paths: Paths = Field(default_factory=Paths)

    @model_validator(mode="after")
    def valid(self) -> Self:
        if self.start > self.end:
            raise ValueError("Zeitraum ist umgekehrt")
        if self.parameters.min_observations > self.limits.max_scenes:
            raise ValueError("Mindestbeobachtungen überschreiten Szenenlimit")
        return self


def load_config(path: Path) -> Config:
    config = Config.model_validate(yaml.safe_load(path.read_text()))
    base = path.resolve().parent
    if config.aoi.geojson is not None:
        config.aoi.geojson = base / config.aoi.geojson
    for name in type(config.paths).model_fields:
        value = getattr(config.paths, name)
        if value is not None:
            setattr(config.paths, name, base / value)
    config.aoi.geometry()
    return config
