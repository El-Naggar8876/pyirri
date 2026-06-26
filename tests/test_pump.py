"""Regression tests for pump hydraulics kernels and pump-curve solver."""
import math

import pytest

from modules.engineering_kernels import (
    total_dynamic_head,
    hydraulic_power_kw,
    brake_power_kw,
    motor_power_kw,
    npsh_margin,
)


def test_tdh_is_sum_of_components():
    # All terms in metres of head -> no unit mixing.
    tdh = total_dynamic_head(static_lift_m=12.0, friction_losses_m=8.5,
                             minor_losses_m=1.5, operating_head_m=28.1)
    assert tdh == pytest.approx(50.1)


def test_hydraulic_power_reference():
    # P = rho g Q H / 1000; Q = 200 m3/h = 0.05556 m3/s, H = 50 m
    p = hydraulic_power_kw(200.0, 50.0)
    assert p == pytest.approx(1000 * 9.81 * (200 / 3600) * 50 / 1000, rel=1e-9)
    assert p == pytest.approx(27.25, abs=0.05)


def test_brake_power_metric_constant():
    # P_kW = Q*H/(367*eff); 200 m3/h, 50 m, 75 %
    p = brake_power_kw(200.0, 50.0, 75.0)
    assert p == pytest.approx(200 * 50 / (367 * 0.75), rel=1e-9)


def test_brake_power_zero_efficiency_guard():
    assert brake_power_kw(200.0, 50.0, 0.0) == 0.0


def test_motor_power_includes_motor_efficiency():
    brake = brake_power_kw(200.0, 50.0, 75.0)
    motor = motor_power_kw(brake, 90.0)
    assert motor == pytest.approx(brake / 0.9, rel=1e-9)
    assert motor > brake


def test_brake_power_exceeds_hydraulic_power():
    q, h, eff = 150.0, 40.0, 70.0
    assert brake_power_kw(q, h, eff) > hydraulic_power_kw(q, h)


def test_npsh_margin_sign():
    assert npsh_margin(7.5, 4.0) == pytest.approx(3.5)
    assert npsh_margin(3.0, 4.0) < 0   # cavitation risk flagged


def test_pump_curve_solver_duty_point():
    pmu = pytest.importorskip("modules.pump_math_utils")
    pump = {
        "id": "TEST-1", "brand": "Test", "model": "T-1",
        "max_flow_m3h": 400.0, "max_head_m": 80.0,
        "bep_flow_m3h": 200.0, "bep_head_m": 50.0, "bep_efficiency": 78.0,
    }
    solver = pmu.PumpCurveSolver(pump)
    assert solver.calculate_head(0.0) >= solver.calculate_head(200.0)
    p = solver.calculate_power(200.0, 50.0, 78.0)
    assert p > 0 and math.isfinite(p)
