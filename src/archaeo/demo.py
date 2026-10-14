from datetime import date
from pathlib import Path
import json
import numpy as np
import rasterio
from rasterio.transform import from_origin
from archaeo.config import AOI, Config
from archaeo.providers.cdse import Scene


def generate(root: Path) -> tuple[Config, list[Scene]]:
    root.mkdir(parents=True, exist_ok=True)
    config = Config(
        aoi=AOI(bbox=(9, 50, 9.009, 50.006)), start=date(2024, 4, 1), end=date(2024, 9, 30)
    )
    config.grid.window_size = 32
    config.paths.output = root.parent.parent / "exports/demo"
    transform = from_origin(500000, 5539200, 10, 10)
    rng = np.random.default_rng(42)
    scenes = []
    for index in range(5):
        red = np.full((64, 64), 0.2)
        nir = np.full((64, 64), 0.5) + rng.normal(0, 0.001, (64, 64))
        # Schmale Struktur über Fenstergrenze; kein archäologisches Modell.
        nir[22:42, 31:33] = 0.25
        scl = np.full((64, 64), 4, dtype="uint8")
        scl[index * 4 : index * 4 + 3, :12] = 9
        red[0:2, :] = np.nan
        for name, array in (("red", red), ("nir", nir), ("scl", scl)):
            with rasterio.open(
                root / f"{index}-{name}.tif",
                "w",
                driver="GTiff",
                height=64,
                width=64,
                count=1,
                dtype=array.dtype,
                crs=config.grid.crs,
                transform=transform,
                nodata=0 if name == "scl" else np.nan,
            ) as dst:
                dst.write(array, 1)
        scenes.append(
            Scene(
                id=f"synthetic-{index}",
                date=date(2024, 5, index + 1),
                red=root / f"{index}-red.tif",
                nir=root / f"{index}-nir.tif",
                scl=root / f"{index}-scl.tif",
                bbox=(9, 50, 9.009, 50.006),
                source_urls=["synthetic://seed-42"],
                band_resolution_m={"B04": 10, "B08": 10, "SCL": 10},
            )
        )
    manifest = [
        {**s.model_dump(mode="json"), "red": s.red.name, "nir": s.nir.name, "scl": s.scl.name}
        for s in scenes
    ]
    (root / "scenes.json").write_text(json.dumps(manifest))
    return config, scenes


def generate_terrain(root: Path) -> tuple[Config, Path]:
    """Kleines synthetisches Relief zum netzwerkfreien Prüfen des Terrainwegs."""
    from pyproj import Transformer
    from archaeo.providers.dem import sha256

    root.mkdir(parents=True, exist_ok=True)
    inverse = Transformer.from_crs(25832, 4326, always_xy=True)
    xmin, ymin = inverse.transform(538002, 5521490)
    xmax, ymax = inverse.transform(538510, 5521998)
    config = Config(
        aoi=AOI(bbox=(xmin, ymin, xmax, ymax)), start=date(2025, 1, 1), end=date(2025, 12, 31)
    )
    y, x = np.mgrid[:512, :512]
    z = 300 + 0.01 * x + 2 * np.sin(y / 90) + 0.7 * np.exp(-(((x - 250) / 3) ** 2))
    z = z.astype("float32")
    z[:5, :] = -9999
    path = root / "synthetic-dtm.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=512,
        height=512,
        count=1,
        dtype="float32",
        crs="EPSG:25832",
        transform=from_origin(538000, 5522000, 1, 1),
        nodata=-9999,
    ) as dst:
        dst.write(z, 1)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": "synthetic; no real terrain",
                "tiles": [{"path": str(path.resolve()), "sha256": sha256(path)}],
            }
        )
    )
    return config, manifest
