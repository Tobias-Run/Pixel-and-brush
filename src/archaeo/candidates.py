"""Vierfach zusammenhängende Komponenten, inklusive Fenstergrenzen.
Score = mittlere absolute NDVI-Abweichung * mittlere Beobachtungszahl / Szenenanzahl.
Konfidenz bezeichnet ausschließlich Datenabdeckung, keine archäologische Wahrscheinlichkeit.
"""

from pathlib import Path
from typing import Any
import numpy as np
import rasterio
from rasterio.features import shapes, geometry_mask
from shapely.geometry import shape, mapping
from archaeo.config import Config


def candidates(
    features: Path, mask: Path, config: Config, scene_count: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with rasterio.open(mask) as source, rasterio.open(features) as data:
        # GDAL polygonisiert das Rasterband statt eines NumPy-Vollbildes.
        for geometry, value in shapes(
            rasterio.band(source, 1), connectivity=4, transform=source.transform
        ):
            if value != 1:
                continue
            polygon = shape(geometry)
            pixels = round(polygon.area / (config.grid.resolution**2))
            if pixels < config.parameters.min_pixels:
                continue
            sums = np.zeros(3)
            count = 0
            # Auch Statistiken großer Komponenten werden blockweise aggregiert.
            for _, window in data.block_windows(1):
                from shapely.geometry import box
                from rasterio.windows import bounds

                if not polygon.intersects(box(*bounds(window, data.transform))):
                    continue
                selected = geometry_mask(
                    [geometry],
                    out_shape=(int(window.height), int(window.width)),
                    transform=data.window_transform(window),
                    invert=True,
                )
                values = data.read([3, 4, 5], window=window)
                count += int(selected.sum())
                sums += np.array(
                    [
                        np.abs(values[0][selected]).sum(),
                        values[1][selected].sum(),
                        values[2][selected].sum(),
                    ]
                )
            deviation, observations, cloud_fraction = sums / count
            confidence = float(observations / scene_count)
            rows.append(
                {
                    "geometry": mapping(polygon),
                    "pixels": pixels,
                    "anomaly_score": float(deviation * confidence),
                    "ndvi_deviation": float(deviation),
                    "observations": float(observations),
                    "cloud_fraction": float(cloud_fraction),
                    "confidence": confidence,
                }
            )
    rows.sort(key=lambda row: row["anomaly_score"], reverse=True)
    for rank, row in enumerate(rows, 1):
        row["id"] = f"candidate-{rank:04d}"
        row["rank"] = rank
    return rows
