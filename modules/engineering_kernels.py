"""
engineering_kernels.py
======================

Pure, dependency-light numerical kernels for OpenIrri.

This module is the single source of truth for the core engineering equations
used across the application (Hazen-Williams head loss, Christiansen F-factor and
uniformity coefficient, total dynamic head, hydraulic/brake power and NPSH
margin). It deliberately imports only the standard library and ``math`` so that
it can be unit-tested in continuous integration without a Streamlit runtime or
any heavyweight GUI/geo dependency.

The Streamlit modules (``pipe_network_design.py``, ``pump_selection.py`` …)
delegate to these functions, guaranteeing that what is tested in
``tests/`` is exactly what runs in the application.

References
----------
* FAO-56 — Allen et al. (1998).
* Williams & Hazen (1920) — Hazen-Williams friction equation.
* Christiansen, J.E. (1942) — sprinkling uniformity & multi-outlet F-factor.
* Keller, J. & Bliesner, R.D. (2001) — Sprinkle and Trickle Irrigation.
"""

from __future__ import annotations

import math

# Hazen-Williams velocity exponent (also used in the Christiansen F-factor).
HW_EXPONENT = 1.852

# Metric pump-power constant: P[kW] = Q[m3/h] * H[m] / (367 * eff) for water (SG=1).
POWER_CONSTANT = 367.0

# Standard gravity and water density.
GRAVITY = 9.81          # m s^-2
RHO_WATER = 1000.0      # kg m^-3

# 1 bar of pressure expressed as metres of water column.
BAR_TO_M = 10.197


# --------------------------------------------------------------------------- #
# Hydraulics
# --------------------------------------------------------------------------- #
def hazen_williams_headloss(Q_m3h: float, D_mm: float, L_m: float, C: float = 130.0) -> float:
    """
    Friction head loss (m) for a single pipe carrying a constant flow.

        h_f = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)

    with Q in m^3 s^-1 and D in m (SI form of the Hazen-Williams equation).
    Returns 0.0 for degenerate (zero flow or zero diameter) input.
    """
    if Q_m3h <= 0 or D_mm <= 0:
        return 0.0
    Q_m3s = Q_m3h / 3600.0
    D_m = D_mm / 1000.0
    return 10.67 * L_m * (Q_m3s ** HW_EXPONENT) / ((C ** HW_EXPONENT) * (D_m ** 4.87))


def velocity_ms(Q_m3h: float, D_mm: float) -> float:
    """Mean flow velocity (m s^-1) for flow Q (m^3/h) in a pipe of bore D (mm)."""
    if D_mm <= 0:
        return 0.0
    Q_m3s = Q_m3h / 3600.0
    area = math.pi * (D_mm / 1000.0) ** 2 / 4.0
    return Q_m3s / area if area > 0 else 0.0


def christiansen_f_factor(n_outlets: int, m: float = HW_EXPONENT) -> float:
    """
    Christiansen multi-outlet reduction factor F for a lateral with ``n_outlets``
    equally spaced, equal-discharge outlets (first outlet one spacing from inlet):

        F = 1/(m+1) + 1/(2N) + sqrt(m-1)/(6 N^2)

    Returns 1.0 for a single outlet (no reduction).
    """
    if n_outlets <= 1:
        return 1.0
    return (1.0 / (m + 1.0)) + (1.0 / (2.0 * n_outlets)) + math.sqrt(m - 1.0) / (6.0 * n_outlets ** 2)


def lateral_headloss(Q_in_m3h: float, D_mm: float, L_m: float, n_outlets: int,
                     C: float = 130.0) -> float:
    """Head loss along a multi-outlet lateral: F * (full-flow Hazen-Williams loss)."""
    hf_full = hazen_williams_headloss(Q_in_m3h, D_mm, L_m, C)
    return christiansen_f_factor(n_outlets) * hf_full


def christiansen_uniformity(catch_values) -> float:
    """
    Christiansen Coefficient of Uniformity (%) from a set of catch-can depths.

        CU = 100 * (1 - sum|Xi - Xbar| / (n * Xbar))

    Raises ValueError for an empty sample; returns 0.0 if the mean is zero.
    """
    vals = [float(x) for x in catch_values]
    n = len(vals)
    if n == 0:
        raise ValueError("catch_values must be non-empty")
    mean = sum(vals) / n
    if mean == 0:
        return 0.0
    abs_dev = sum(abs(x - mean) for x in vals)
    cu = 100.0 * (1.0 - abs_dev / (n * mean))
    return cu


# --------------------------------------------------------------------------- #
# Pump hydraulics
# --------------------------------------------------------------------------- #
def total_dynamic_head(static_lift_m: float, friction_losses_m: float,
                       minor_losses_m: float, operating_head_m: float) -> float:
    """
    Total Dynamic Head (m), all terms expressed as metres of water column:

        TDH = h_static + h_friction + h_minor + h_operating

    ``operating_head_m`` is the required sprinkler nozzle pressure converted to
    head (divide nozzle pressure in kPa by 9.81, or in bar by 10.197 -> m).
    """
    return static_lift_m + friction_losses_m + minor_losses_m + operating_head_m


def hydraulic_power_kw(Q_m3h: float, head_m: float) -> float:
    """Water (hydraulic) power in kW: P = rho * g * Q * H / 1000, Q in m^3 s^-1."""
    Q_m3s = Q_m3h / 3600.0
    return RHO_WATER * GRAVITY * Q_m3s * head_m / 1000.0


def brake_power_kw(Q_m3h: float, head_m: float, pump_efficiency_percent: float) -> float:
    """
    Brake (shaft) power in kW using the metric pump constant:

        P_kW = Q[m3/h] * H[m] / (367 * eff)

    Returns 0.0 for non-positive efficiency.
    """
    if pump_efficiency_percent <= 0:
        return 0.0
    return (Q_m3h * head_m) / (POWER_CONSTANT * (pump_efficiency_percent / 100.0))


def motor_power_kw(brake_kw: float, motor_efficiency_percent: float) -> float:
    """Electrical input power (kW) from brake power and motor efficiency."""
    if motor_efficiency_percent <= 0:
        return 0.0
    return brake_kw / (motor_efficiency_percent / 100.0)


def npsh_margin(npsh_available_m: float, npsh_required_m: float) -> float:
    """NPSH safety margin (m) = NPSH_available - NPSH_required (>0 means safe)."""
    return npsh_available_m - npsh_required_m


# --------------------------------------------------------------------------- #
# Pipe sizing (velocity-constrained, deterministic iteration)
# --------------------------------------------------------------------------- #
STANDARD_PVC_SIZES = [
    {"nominal": 20, "internal": 17.6}, {"nominal": 25, "internal": 22.0},
    {"nominal": 32, "internal": 28.0}, {"nominal": 40, "internal": 35.2},
    {"nominal": 50, "internal": 44.0}, {"nominal": 63, "internal": 55.4},
    {"nominal": 75, "internal": 66.0}, {"nominal": 90, "internal": 79.2},
    {"nominal": 110, "internal": 96.8}, {"nominal": 125, "internal": 110.0},
    {"nominal": 140, "internal": 123.2}, {"nominal": 160, "internal": 140.8},
    {"nominal": 200, "internal": 176.0}, {"nominal": 250, "internal": 220.0},
    {"nominal": 315, "internal": 277.2},
]


def select_pipe_diameter(Q_m3h: float, max_velocity_ms: float = 2.0,
                         min_velocity_ms: float = 0.6, sizes=None) -> dict:
    """
    Deterministically pick the smallest standard pipe whose mean velocity at flow
    ``Q_m3h`` does not exceed ``max_velocity_ms`` (the economic-velocity rule).

    Returns the selected size dict augmented with the resulting velocity and a
    ``converged`` flag. If even the largest pipe exceeds the cap, the largest
    pipe is returned with ``converged=False`` so callers can warn the user
    (no silent failure / no infinite loop).
    """
    sizes = sizes or STANDARD_PVC_SIZES
    for size in sizes:
        v = velocity_ms(Q_m3h, size["internal"])
        if v <= max_velocity_ms:
            return {**size, "velocity_ms": v,
                    "converged": True,
                    "below_min_velocity": v < min_velocity_ms}
    largest = sizes[-1]
    return {**largest, "velocity_ms": velocity_ms(Q_m3h, largest["internal"]),
            "converged": False, "below_min_velocity": False}


def lateral_pressure_variation_ok(hf_lateral_m: float, nozzle_head_m: float,
                                  limit_fraction: float = 0.20) -> bool:
    """
    Keller-Bliesner / FAO criterion: lateral pressure must not vary by more than
    ``limit_fraction`` (default 20 %) of the nozzle operating head.
    """
    if nozzle_head_m <= 0:
        return False
    return (hf_lateral_m / nozzle_head_m) <= limit_fraction
