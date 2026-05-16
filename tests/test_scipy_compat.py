import numpy as np

from scipy.stats import linregress


def test_linregress_returns_slope_and_r_value():
    slope, intercept, r_value, p_value, stderr = linregress(np.array([0, 1, 2]), np.array([1, 3, 5]))

    assert slope == 2
    assert intercept == 1
    assert r_value == 1
    assert np.isnan(p_value)
    assert stderr == 0
