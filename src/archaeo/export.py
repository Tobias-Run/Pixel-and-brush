import csv
import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.warp import transform_geom
from shapely.geometry import shape
from archaeo.config import Config
from archaeo.providers.cdse import Scene
from archaeo import __version__

FORMULA = "Score = mean(abs(NDVI-Median − lokaler Median)) × mean(Beobachtungszahl)/Szenenanzahl."


def export(
    rows: list[dict[str, Any]], config: Config, scenes: list[Scene], gaps: list[str]
) -> None:
    out = config.paths.output
    out.mkdir(parents=True, exist_ok=True)
    metadata = {
        "scene_bboxes": [s.bbox for s in scenes],
        "source_ids": [s.id for s in scenes],
        "source_urls": [url for s in scenes for url in s.source_urls],
        "parameters": config.parameters.model_dump(),
        "band_resolution_m": [s.band_resolution_m for s in scenes],
    }
    exported = []
    for row in rows:
        properties = {k: v for k, v in row.items() if k != "geometry"}
        properties.update(metadata)
        exported.append(
            {
                "type": "Feature",
                "geometry": transform_geom(config.grid.crs, "EPSG:4326", row["geometry"]),
                "properties": properties,
            }
        )
    # RFC 7946: GeoJSON immer WGS84, kein veraltetes crs-Feld.
    (out / "candidates.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": exported}, allow_nan=False)
    )
    fields = [
        "id",
        "rank",
        "anomaly_score",
        "ndvi_deviation",
        "observations",
        "cloud_fraction",
        "confidence",
        "pixels",
        "register_overlap",
        "polygon_wgs84",
        *metadata.keys(),
    ]
    with (out / "candidates.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in exported:
            props = item["properties"].copy()
            props["polygon_wgs84"] = item["geometry"]
            writer.writerow(
                {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in props.items()}
            )
    fig, ax = plt.subplots(figsize=(6, 5))
    for row in rows:
        polygon = shape(row["geometry"])
        x, y = polygon.exterior.xy
        ax.fill(x, y, alpha=0.5)
        ax.annotate(row["id"], (polygon.centroid.x, polygon.centroid.y), fontsize=6)
    ax.set_aspect("equal")
    ax.set_title("Statistische Kandidaten (keine Fundplätze)")
    ax.set_xlabel(f"Ost [m], {config.grid.crs}")
    ax.set_ylabel("Nord [m]")
    fig.tight_layout()
    fig.savefig(out / "map.png", dpi=140)
    plt.close(fig)

    def digest(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                h.update(block)
        return h.hexdigest()

    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "versions": {
            p: version(p) for p in ("numpy", "rasterio", "geopandas", "pyproj", "pydantic")
        },
        "config": config.model_dump(mode="json"),
        "sources": [s.model_dump(mode="json") for s in scenes],
        "input_sha256": {str(p): digest(p) for s in scenes for p in (s.red, s.nir, s.scl)},
        "formula": FORMULA,
        "gaps": gaps,
        "candidate_count": len(rows),
        "output_crs": "EPSG:4326",
        "connectivity": 4,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False))
    (out / "report.md").write_text(
        f"""# Prospektionsbericht
{len(rows)} statistische Kandidaten. Keine archäologischen Fundplätze oder Wahrscheinlichkeiten.

![Lokale Kandidatenkarte](map.png)

## Methode
NDVI = (B08 − B04)/(B08 + B04). Nullnenner sind ungültig.
Zeitmedian und Standardabweichung; räumlicher Median im quadratischen Kontextfenster.
{FORMULA}
Schwelle: {config.parameters.threshold}; Mindestbeobachtungen: {config.parameters.min_observations};
Mindestgröße: {config.parameters.min_pixels} Pixel; Kontextradius: {config.parameters.context_radius} Pixel.
Zu wenige Beobachtungen: nicht bewertbar (features.tif Band 6), keine Anomalie.
SCL 3/8/9/10: Schatten/Wolken; 0/1/11: ungültig/Schnee. Kein DEM verwendet.
Zielraster: {config.grid.resolution} m, {config.grid.crs}. Originalauflösungen im Manifest.
Abweichung im Export ist der mittlere Absolutbetrag; signierte Werte stehen in features.tif.
Konfidenz ist Datenabdeckung. Wolkenanteil bezieht sich auf alle verwendeten Szenen.

## Datenlücken
"""
        + "\n".join(f"- {gap}" for gap in gaps)
        + "\n\nParameter sind nicht wissenschaftlich validiert. Tests prüfen Softwarekorrektheit.\nCopernicus/ESA bei echten Sentinel-Daten attribuieren. Vor Feldarbeit Denkmalbehörde kontaktieren.\n"
    )
