from contextlib import ExitStack
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from shapely.geometry import mapping
from archaeo.config import Config
from archaeo.providers.cdse import Scene
from archaeo.preprocessing import assert_aligned, ndvi
from archaeo.features import features, FEATURE_NAMES
from archaeo.errors import PipelineError


def calculate(config: Config, scenes: list[Scene], output: Path) -> tuple[Path, Path]:
    if not scenes or len(scenes) > config.limits.max_scenes:
        raise PipelineError("Keine Szenen oder Szenenlimit überschritten")
    output.mkdir(parents=True, exist_ok=True)
    feature_path, mask_path = output / "features.tif", output / "anomalies.tif"
    with ExitStack() as context:
        datasets = [
            [context.enter_context(rasterio.open(p)) for p in (s.red, s.nir, s.scl)] for s in scenes
        ]
        ref = datasets[0][0]
        for bands in datasets:
            for dataset in bands:
                assert_aligned(ref, dataset)
        if ref.width * ref.height > config.limits.max_pixels:
            raise PipelineError("Pixel-Limit überschritten")
        if ref.crs != rasterio.crs.CRS.from_string(config.grid.crs):
            raise PipelineError("CRS-Mismatch zum Zielraster")
        if ref.res != (config.grid.resolution, config.grid.resolution):
            raise PipelineError("Auflösungs-Mismatch zum Zielraster")
        if ref.transform.b != 0 or ref.transform.d != 0:
            raise PipelineError("Gedrehte Raster werden im MVP nicht unterstützt")
        aoi = transform_geom("EPSG:4326", ref.crs, mapping(config.aoi.geometry()))
        profile = ref.profile.copy()
        profile.update(
            driver="GTiff",
            count=6,
            dtype="float64",
            nodata=np.nan,
            tiled=True,
            blockxsize=128,
            blockysize=128,
            compress="deflate",
        )
        dst = context.enter_context(rasterio.open(feature_path, "w", **profile))
        for i, name in enumerate(FEATURE_NAMES, 1):
            dst.set_band_description(i, name)
        profile.update(count=1, dtype="uint8", nodata=0)
        mask_dst = context.enter_context(rasterio.open(mask_path, "w", **profile))
        total_valid = 0
        size, radius = config.grid.window_size, config.parameters.context_radius
        for y in range(0, ref.height, size):
            for x in range(0, ref.width, size):
                width, height = min(size, ref.width - x), min(size, ref.height - y)
                left, top = max(0, x - radius), max(0, y - radius)
                right, bottom = (
                    min(ref.width, x + width + radius),
                    min(ref.height, y + height + radius),
                )
                expanded = Window(left, top, right - left, bottom - top)
                inside = geometry_mask(
                    [aoi],
                    out_shape=(bottom - top, right - left),
                    transform=ref.window_transform(expanded),
                    invert=True,
                )
                values, clouds = [], []
                for red, nir, scl in datasets:
                    arrays = [
                        np.asarray(
                            d.read(1, window=expanded, masked=True).astype("float64").filled(np.nan)
                        )
                        for d in (red, nir, scl)
                    ]
                    value, cloud = ndvi(*arrays)
                    value[~inside] = np.nan
                    values.append(value)
                    clouds.append(cloud)
                result = features(
                    np.stack(values), np.stack(clouds), radius, config.parameters.min_observations
                )
                crop = result[:, y - top : y - top + height, x - left : x - left + width]
                window = Window(x, y, width, height)
                total_valid += int(np.nansum(crop[3]))
                dst.write(crop, window=window)
                anomaly = (np.abs(crop[2]) >= config.parameters.threshold) & (crop[5] == 1)
                mask_dst.write(anomaly.astype("uint8"), 1, window=window)
        if total_valid == 0:
            raise PipelineError("Vollständig ungültige Raster oder keine AOI-Überdeckung")
    return feature_path, mask_path
