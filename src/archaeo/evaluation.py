"""Optionale lokale Referenzen; fehlende Daten werden als Lücken dokumentiert."""

from pathlib import Path
from typing import Any
import geopandas as gpd
from shapely.geometry import shape
from archaeo.config import Config
from archaeo.errors import PipelineError


def evaluate(rows: list[dict[str, Any]], config: Config) -> list[str]:
    gaps: list[str] = []
    for name in ("register", "landuse", "historical_map"):
        path: Path | None = getattr(config.paths, "register_file" if name == "register" else name)
        if path is None or not path.exists():
            gaps.append(f"{name}: keine lokale Referenz vorhanden")
        elif name == "register":
            if path.suffix.lower() == ".csv":
                import csv
                from shapely.geometry import Point

                with path.open() as stream:
                    records = list(csv.DictReader(stream))
                try:
                    register = gpd.GeoDataFrame(
                        geometry=[
                            Point(float(v["longitude"]), float(v["latitude"])) for v in records
                        ],
                        crs="EPSG:4326",
                    )
                except (KeyError, ValueError) as exc:
                    raise PipelineError(
                        "Register-CSV benötigt longitude, latitude in WGS84"
                    ) from exc
            else:
                register = gpd.read_file(path)
            if (
                register.crs is None
                or register.geometry.is_empty.any()
                or not register.geometry.is_valid.all()
            ):
                raise PipelineError("Register ohne CRS oder mit ungültiger Geometrie")
            register = register.to_crs(config.grid.crs)
            for row in rows:
                row["register_overlap"] = bool(register.intersects(shape(row["geometry"])).any())
        else:
            gaps.append(
                f"{name}: lokale Referenz {path.name} vorhanden; manuelle Prüfung erforderlich"
            )
    return gaps
