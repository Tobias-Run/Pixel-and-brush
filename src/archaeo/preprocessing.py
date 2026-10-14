from typing import Any
import numpy as np
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.warp import reproject
from archaeo.errors import PipelineError

FloatArray = NDArray[np.float64]


def assert_aligned(reference: Any, other: Any) -> None:
    if reference.crs is None or reference.crs != other.crs:
        raise PipelineError("CRS-Mismatch oder fehlendes CRS")
    if reference.shape != other.shape or reference.transform != other.transform:
        raise PipelineError("Auflösungs-/Ausrichtungs-Mismatch; explizit resampeln")


def resample(
    source: FloatArray,
    source_transform: Any,
    target_transform: Any,
    source_crs: str,
    target_crs: str,
    shape: tuple[int, int],
    categorical: bool = False,
) -> FloatArray:
    result = np.full(shape, np.nan)
    reproject(
        source,
        result,
        src_transform=source_transform,
        dst_transform=target_transform,
        src_crs=source_crs,
        dst_crs=target_crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.nearest if categorical else Resampling.bilinear,
    )
    return result


def ndvi(red: FloatArray, nir: FloatArray, scl: FloatArray) -> tuple[FloatArray, NDArray[np.bool_]]:
    cloud = np.isin(scl, [3, 8, 9, 10])
    valid = np.isin(scl, [2, 4, 5, 6, 7]) & np.isfinite(red) & np.isfinite(nir)
    valid &= (red >= 0) & (nir >= 0) & ((red + nir) != 0)
    result = np.full(red.shape, np.nan)
    np.divide(nir - red, nir + red, out=result, where=valid)
    return result, cloud
