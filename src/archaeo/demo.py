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
