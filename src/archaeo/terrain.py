"""Fensterweises 1-m-Hillshade und überlappende Bildpakete zur lokalen Vorprüfung.

Vier Beleuchtungsrichtungen, Sonnenhöhe 35 Grad, z-Faktor 1 (Meter/ Meter).
Keine Anomalie- oder Fundstellenklassifikation. Kein Höhenmodell-Upsampling.
"""

import json
from datetime import datetime, timezone
from importlib.metadata import version
import math
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
import rasterio
from rasterio.features import geometry_mask
from rasterio.merge import merge
from rasterio.warp import transform_bounds, transform_geom
from rasterio.windows import Window, bounds
from shapely.geometry import mapping
from PIL import Image, ImageDraw

from archaeo.config import Config
from archaeo.errors import PipelineError
from archaeo.providers.dem import sha256

AZIMUTHS = (45, 135, 225, 315)


def hillshade(
    elevation: NDArray[np.float64], resolution: float, azimuth: float, altitude: float = 35
) -> NDArray[np.float64]:
    """Lambert-Beleuchtung des Oberflächennormalenvektors; Norden ist Zeile -1."""
    if resolution <= 0 or min(elevation.shape) < 3:
        raise PipelineError("Hillshade benötigt positives Rastermaß und mindestens 3×3 Pixel")
    dy, dx = np.gradient(elevation, resolution)
    az, alt = math.radians(azimuth), math.radians(altitude)
    dot = -dx * math.sin(az) * math.cos(alt) + dy * math.cos(az) * math.cos(alt) + math.sin(alt)
    return np.asarray(np.clip(dot / np.sqrt(1 + dx * dx + dy * dy), 0, 1), dtype=np.float64)


def prepare_terrain(
    config: Config,
    manifest_path: Path,
    tile_size: int = 512,
    overlap: int = 64,
    max_pixels: int = 40000000,
) -> Path:
    if not 128 <= tile_size <= 1024 or not 0 <= overlap < tile_size:
        raise PipelineError("Tilegröße 128–1024; Überlappung kleiner als Tilegröße")
    if max_pixels < 1:
        raise PipelineError("Terrain-Pixellimit muss positiv sein")
    source_manifest = json.loads(manifest_path.read_text())
    records = source_manifest.get("tiles", [])
    if not records:
        raise PipelineError("DEM-Manifest enthält keine Kacheln")
    out = config.paths.output / "terrain"
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").unlink(missing_ok=True)
    with ExitStack() as context:
        sources: list[Any] = []
        for record in records:
            path = Path(record["path"])
            if sha256(path) != record["sha256"]:
                raise PipelineError("DEM-Prüfsumme stimmt nicht")
            source = context.enter_context(rasterio.open(path))
            if (
                source.crs != rasterio.crs.CRS.from_epsg(25832)
                or source.res != (1, 1)
                or source.count != 1
                or source.transform.b != 0
                or source.transform.d != 0
                or source.transform.a != 1
                or source.transform.e != -1
            ):
                raise PipelineError("DGM1 erfordert ausgerichtetes 1-m-Raster in EPSG:25832")
            if sources:
                origin = sources[0].transform
                if (
                    not float(source.transform.c - origin.c).is_integer()
                    or not float(source.transform.f - origin.f).is_integer()
                ):
                    raise PipelineError("DEM-Ausrichtungsfehler")
            sources.append(source)
        aoi = mapping(config.aoi.geometry())
        aoi_projected = transform_geom("EPSG:4326", "EPSG:25832", aoi)
        from shapely.geometry import shape

        bbox = shape(aoi).bounds
        box = transform_bounds("EPSG:4326", "EPSG:25832", *bbox)
        box = (
            math.floor(box[0]) - 1,
            math.floor(box[1]) - 1,
            math.ceil(box[2]) + 1,
            math.ceil(box[3]) + 1,
        )
        if (box[2] - box[0]) * (box[3] - box[1]) > max_pixels:
            raise PipelineError("Terrain-Pixellimit überschritten")
        mosaic = out / "dgm1.tif"
        merge(
            sources,
            bounds=box,
            res=1,
            nodata=-9999,
            dtype="float32",
            mem_limit=32,
            dst_path=mosaic,
            dst_kwds={"tiled": True, "blockxsize": 256, "blockysize": 256, "compress": "deflate"},
        )
    shade_path = out / "hillshade.tif"
    valid_count = 0
    with rasterio.open(mosaic) as source:
        profile = source.profile.copy()
        profile.update(count=4, dtype="uint8", nodata=0)
        with rasterio.open(shade_path, "w", **profile) as dst:
            for i, az in enumerate(AZIMUTHS, 1):
                dst.set_band_description(i, f"azimuth_{az}_altitude_35")
            for _, window in dst.block_windows(1):
                x, y = int(window.col_off), int(window.row_off)
                width, height = int(window.width), int(window.height)
                expanded = Window(x - 1, y - 1, width + 2, height + 2)
                z = np.asarray(
                    source.read(1, window=expanded, boundless=True, masked=True)
                    .astype("float64")
                    .filled(np.nan)
                )
                valid = np.isfinite(np.lib.stride_tricks.sliding_window_view(z, (3, 3))).all(
                    axis=(-2, -1)
                )
                valid &= geometry_mask(
                    [aoi_projected],
                    out_shape=(height, width),
                    transform=source.window_transform(window),
                    invert=True,
                )
                valid_count += int(valid.sum())
                for i, az in enumerate(AZIMUTHS, 1):
                    illumination = hillshade(z, 1, az)[1:-1, 1:-1]
                    pixels = np.zeros((height, width), dtype="uint8")
                    pixels[valid] = (1 + 254 * illumination[valid]).astype("uint8")
                    dst.write(pixels, i, window=window)
    if not valid_count:
        raise PipelineError("DEM vollständig ungültig oder keine AOI-Überdeckung")
    for stale in (out / "tiles").glob("batch-*/terrain-*.png"):
        stale.unlink()
    tiles: list[dict[str, Any]] = []
    with rasterio.open(shade_path) as source:
        step = tile_size - overlap
        for y in range(0, source.height, step):
            for x in range(0, source.width, step):
                window = Window(
                    x, y, min(tile_size, source.width - x), min(tile_size, source.height - y)
                )
                pixels = source.read(window=window)
                fraction = float((pixels[0] > 0).mean())
                if fraction < 0.5:
                    continue
                batch = out / "tiles" / f"batch-{len(tiles) // 20 + 1:03d}"
                batch.mkdir(parents=True, exist_ok=True)
                canvas = Image.new("RGB", (2 * tile_size, 2 * (tile_size + 24)), "white")
                drawing = ImageDraw.Draw(canvas)
                for i, az in enumerate(AZIMUTHS):
                    ox, oy = (i % 2) * tile_size, (i // 2) * (tile_size + 24)
                    image = Image.fromarray(pixels[i]).convert("RGB")
                    canvas.paste(image, (ox, oy + 24))
                    drawing.text((ox + 4, oy + 4), f"Az {az}, alt 35 | 1 px = 1 m", fill="black")
                name = f"terrain-{len(tiles) + 1:04d}.png"
                image_path = batch / name
                canvas.save(image_path)
                tiles.append(
                    {
                        "image": str(image_path.relative_to(out)),
                        "sha256": sha256(image_path),
                        "bounds_epsg25832": bounds(window, source.transform),
                        "valid_fraction": fraction,
                        "window": [x, y, window.width, window.height],
                    }
                )
    target = out / "manifest.json"
    target.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "versions": {
                    name: version(name) for name in ("numpy", "rasterio", "pyproj", "pillow")
                },
                "raster_sha256": {"dgm1.tif": sha256(mosaic), "hillshade.tif": sha256(shade_path)},
                "sources": source_manifest,
                "crs": "EPSG:25832",
                "resolution_m": 1,
                "azimuths": AZIMUTHS,
                "altitude": 35,
                "z_factor": 1,
                "tile_size": tile_size,
                "overlap": overlap,
                "valid_pixels": valid_count,
                "tiles": tiles,
                "warning": "Hillshade zur visuellen Prüfung, keine Fundstellen",
            },
            indent=2,
        )
    )
    import html

    source_label = html.escape(source_manifest.get("attribution", "Synthetische Testdaten"))
    license_label = html.escape(source_manifest.get("license", "projektgeneriert"))
    cards = "\n".join(
        f'<a href="{html.escape(v["image"], quote=True)}"><img loading="lazy" '
        f'src="{html.escape(v["image"], quote=True)}" alt="Hillshade-Ausschnitt">'
        f"<span>{html.escape(Path(v['image']).stem)}</span></a>"
        for v in tiles
    )
    (out / "overview.html").write_text(
        '<!doctype html><html lang="de"><meta charset="utf-8"><title>Terrain-Bildpakete</title>'
        "<style>body{font-family:system-ui;margin:2rem}main{display:grid;"
        "grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}"
        "img{width:100%}a{color:inherit}span{display:block}</style>"
        "<h1>Terrain-Bildpakete zur manuellen Prüfung</h1>"
        f"<p>Quelle: {source_label}, {license_label}. Vier Beleuchtungsrichtungen; "
        "keine archäologische Bewertung. Bild anklicken für volle Größe. "
        "Aufnahmejahre noch prüfen. Überlappende Bilder enthalten dieselben Geländeformen.</p>"
        f"<p>{len(tiles)} Bildpakete, {valid_count:,} gültige 1-m-Pixel.</p><main>{cards}</main>"
        "</html>",
        encoding="utf-8",
    )
    (out / "report.md").write_text(
        f"# Terrain-Vorbereitung\n\n{len(tiles)} Bildpakete, {valid_count:,} gültige Pixel.\n\n"
        "[Lokale Bildübersicht](overview.html). Keine Kandidatenklassifikation erfolgt.\n\n"
        f"Quelle: {source_manifest.get('attribution', 'Synthetische Testdaten')}; "
        f"Lizenz: {source_manifest.get('license', 'projektgeneriert')}.\n\n"
        "1-m-DTM, EPSG:25832. Vier Azimute 45/135/225/315°, Sonnenhöhe 35°, "
        "z-Faktor 1. Lambert-Beleuchtung aus zentralen Höhengradienten; "
        "NoData und Nachbarschaften ohne vollständige 3×3-Werte sind ungültig.\n"
        f"Ausschnitte: {tile_size} Pixel, Überlappung {overlap}; mindestens 50% gültig. "
        "Schwarz markiert ungültige Bereiche; dunkle gültige Schatten liegen nahe Schwarz.\n\n"
        "Aufnahmejahr und lokale Datenqualität nachprüfen. Hochrechnung auf archäologische "
        "Erkennungsleistung ist unzulässig. Höhenbezug und Quellen stehen im Manifest.\n",
        encoding="utf-8",
    )
    return target
