"""NumPy-backed replacement for scipy.stats.linregress."""

from __future__ import annotations

import numpy as np


def linregress(x, y):
    """Return slope, intercept, r-value, p-value, and slope standard error."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)

    if x_arr.shape != y_arr.shape:
        raise ValueError("x and y must have the same shape")
    if x_arr.size < 2:
        raise ValueError("At least two data points are required")

    x_mean = np.mean(x_arr)
    y_mean = np.mean(y_arr)
    ssxm = np.sum((x_arr - x_mean) ** 2)
    ssym = np.sum((y_arr - y_mean) ** 2)
    ssxym = np.sum((x_arr - x_mean) * (y_arr - y_mean))

    if ssxm == 0:
        raise ValueError("Cannot calculate a linear regression if all x values are identical")

    slope = ssxym / ssxm
    intercept = y_mean - slope * x_mean
    r_value = 0.0 if ssym == 0 else ssxym / np.sqrt(ssxm * ssym)

    if x_arr.size <= 2:
        stderr = np.nan
    else:
        residuals = y_arr - (slope * x_arr + intercept)
        stderr = np.sqrt(np.sum(residuals**2) / ((x_arr.size - 2) * ssxm))

    return slope, intercept, r_value, np.nan, stderr
