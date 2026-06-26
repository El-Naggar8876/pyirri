"""
Deterministic regression tests for the hydraulic kernels.

Reference values are independently re-derived from the closed-form
Hazen-Williams and Christiansen equations and (for the multi-outlet lateral)
cross-checked against the EPANET 2.2 solver in
``validation/hydraulic_benchmark.py``.
"""
import math

import pytest

from modules.engineering_kernels import (
    hazen_williams_headloss,
    christiansen_f_factor,
    christiansen_uniformity,
    lateral_headloss,
    velocity_ms,
    lateral_pressure_variation_ok,
)


def _hw_reference(Q_m3h, D_mm, L_m, C):
    Q = Q_m3h / 3600.0
    D = D_mm / 1000.0
    return 10.67 * L_m * Q ** 1.852 / (C ** 1.852 * D ** 4.87)


@pytest.mark.parametrize("Q,D,L,C", [
    (200.0, 176.0, 270.0, 150.0),
    (109.0, 140.8, 177.0, 150.0),
    (16.64, 55.4, 403.2, 150.0),
    (3.6, 22.0, 50.0, 130.0),
])
def test_hazen_williams_matches_closed_form(Q, D, L, C):
    got = hazen_williams_headloss(Q, D, L, C)
    exp = _hw_reference(Q, D, L, C)
    assert math.isclose(got, exp, rel_tol=1e-9)


def test_hazen_williams_scales_with_length():
    a = hazen_williams_headloss(50, 96.8, 100, 150)
    b = hazen_williams_headloss(50, 96.8, 200, 150)
    assert math.isclose(b, 2 * a, rel_tol=1e-9)


def test_hazen_williams_zero_flow_or_diameter_is_zero():
    assert hazen_williams_headloss(0, 100, 50, 150) == 0.0
    assert hazen_williams_headloss(50, 0, 50, 150) == 0.0


def test_hazen_williams_rejects_no_negative_blowup():
    assert hazen_williams_headloss(-5, 100, 50, 150) == 0.0


def test_f_factor_single_outlet_is_one():
    assert christiansen_f_factor(1) == 1.0
    assert christiansen_f_factor(0) == 1.0


def test_f_factor_known_values():
    # Standard Christiansen F-factor values for m = 1.852 (three-term form).
    assert christiansen_f_factor(10) == pytest.approx(0.402, abs=2e-3)
    assert christiansen_f_factor(20) == pytest.approx(0.376, abs=2e-3)
    assert christiansen_f_factor(1000) == pytest.approx(1 / (1.852 + 1), abs=1e-3)


def test_f_factor_monotonic_decreasing():
    vals = [christiansen_f_factor(n) for n in (2, 5, 10, 30, 100)]
    assert all(earlier > later for earlier, later in zip(vals, vals[1:]))


def test_lateral_headloss_equals_F_times_full_flow():
    Q, D, L, n, C = 16.64, 55.4, 403.2, 32, 150.0
    expected = christiansen_f_factor(n) * hazen_williams_headloss(Q, D, L, C)
    assert math.isclose(lateral_headloss(Q, D, L, n, C), expected, rel_tol=1e-12)


def test_uniformity_perfectly_uniform_is_100():
    assert christiansen_uniformity([10, 10, 10, 10]) == pytest.approx(100.0)


def test_uniformity_worked_example():
    # Mean = 10; sum|dev| = 2+1+0+1+2 = 6; CU = 100*(1 - 6/(5*10)) = 88.0
    catches = [8, 9, 10, 11, 12]
    assert christiansen_uniformity(catches) == pytest.approx(88.0, abs=1e-6)


def test_uniformity_empty_raises():
    with pytest.raises(ValueError):
        christiansen_uniformity([])


def test_uniformity_all_zero_returns_zero():
    assert christiansen_uniformity([0, 0, 0]) == 0.0


def test_velocity_known_value():
    v = velocity_ms(200.0, 176.0)
    assert v == pytest.approx(2.284, abs=1e-3)


def test_lateral_pressure_variation_criterion():
    assert lateral_pressure_variation_ok(5.0, 28.0) is True
    assert lateral_pressure_variation_ok(7.0, 28.0) is False
    assert lateral_pressure_variation_ok(5.0, 0.0) is False
