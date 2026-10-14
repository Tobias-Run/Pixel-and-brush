"""NDVI-Zeitmedian, Standardabweichung und lokaler räumlicher Median."""

import warnings
import numpy as np
from numpy.typing import NDArray
from archaeo.preprocessing import FloatArray

FEATURE_NAMES = ("median", "spread", "deviation", "observations", "cloud_fraction", "assessable")


def features(
    stack: FloatArray, clouds: NDArray[np.bool_], radius: int, min_observations: int
) -> FloatArray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(stack, axis=0)
        spread = np.nanstd(stack, axis=0)
        padded = np.pad(median, radius, constant_values=np.nan)
        views = np.lib.stride_tricks.sliding_window_view(padded, (2 * radius + 1, 2 * radius + 1))
        local = np.nanmedian(views, axis=(-2, -1))
    count = np.isfinite(stack).sum(axis=0)
    assessable = (count >= min_observations) & np.isfinite(local)
    deviation = np.where(assessable, median - local, np.nan)
    return np.stack([median, spread, deviation, count, clouds.mean(axis=0), assessable])
