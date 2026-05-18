"""Small TA-Lib compatibility subset used by copied strategies."""

from __future__ import annotations

import numpy as np


def ATR(high, low, close, timeperiod=14):
    """Return Average True Range using TA-Lib-like ndarray semantics."""
    high_values = np.asarray(high, dtype=float)
    low_values = np.asarray(low, dtype=float)
    close_values = np.asarray(close, dtype=float)
    if not (len(high_values) == len(low_values) == len(close_values)):
        raise ValueError("high, low, and close must have the same length")
    if timeperiod <= 0:
        raise ValueError("timeperiod must be positive")
    if len(close_values) == 0:
        return np.asarray([], dtype=float)

    previous_close = np.empty_like(close_values)
    previous_close[0] = np.nan
    previous_close[1:] = close_values[:-1]
    true_range = np.nanmax(
        np.vstack(
            [
                high_values - low_values,
                np.abs(high_values - previous_close),
                np.abs(low_values - previous_close),
            ]
        ),
        axis=0,
    )
    result = np.full(len(true_range), np.nan, dtype=float)
    for index in range(timeperiod - 1, len(true_range)):
        result[index] = np.nanmean(true_range[index - timeperiod + 1 : index + 1])
    return result


__all__ = ["ATR"]
