"""
Edge-case and robustness tests (Reviewer #1, comment 3).

Covers: extreme wind de-rating of uniformity, irregular/degenerate field
geometry, deterministic convergence of the pipe-diameter selection loop, and
graceful handling of out-of-range hydraulic input.
"""
import pytest

from modules.engineering_kernels import (
    select_pipe_diameter,
    velocity_ms,
    christiansen_uniformity,
    hazen_williams_headloss,
    STANDARD_PVC_SIZES,
)


# --------------------------------------------------------------------------- #
# Pipe-diameter selection: convergence & extreme flow
# --------------------------------------------------------------------------- #
def test_pipe_selection_picks_smallest_within_velocity_cap():
    sel = select_pipe_diameter(16.64, max_velocity_ms=2.0)
    assert sel["converged"] is True
    assert sel["velocity_ms"] <= 2.0
    # Selecting the next-smaller pipe would violate the cap (smallest valid).
    sizes = STANDARD_PVC_SIZES
    idx = next(i for i, s in enumerate(sizes) if s["nominal"] == sel["nominal"])
    if idx > 0:
        smaller = sizes[idx - 1]
        assert velocity_ms(16.64, smaller["internal"]) > 2.0


def test_pipe_selection_extreme_flow_does_not_hang():
    # Flow far beyond the largest pipe: must return largest with converged=False,
    # never loop forever or raise.
    sel = select_pipe_diameter(100000.0, max_velocity_ms=2.0)
    assert sel["converged"] is False
    assert sel["nominal"] == STANDARD_PVC_SIZES[-1]["nominal"]


def test_pipe_selection_zero_flow():
    sel = select_pipe_diameter(0.0, max_velocity_ms=2.0)
    assert sel["converged"] is True
    assert sel["velocity_ms"] == 0.0


# --------------------------------------------------------------------------- #
# Extreme wind: uniformity de-rating stays physical
# --------------------------------------------------------------------------- #
def test_extreme_wind_reduces_uniformity_but_stays_bounded():
    # Simulate a wind-skewed catch pattern (downwind cans collect much less).
    calm = [10, 10, 10, 10, 10, 10]
    windy = [4, 6, 9, 11, 14, 16]   # same mean (10), high spread
    cu_calm = christiansen_uniformity(calm)
    cu_windy = christiansen_uniformity(windy)
    assert cu_calm == pytest.approx(100.0)
    assert cu_windy < cu_calm
    assert 0.0 <= cu_windy <= 100.0


def test_severe_wind_low_uniformity():
    # Strongly skewed pattern -> CU well below the 85 % design threshold.
    severe = [2, 3, 5, 12, 18, 20]
    assert christiansen_uniformity(severe) < 85.0


# --------------------------------------------------------------------------- #
# Irregular / degenerate field geometry (shapely)
# --------------------------------------------------------------------------- #
def test_irregular_polygon_area_is_positive():
    shapely = pytest.importorskip("shapely.geometry")
    Polygon = shapely.Polygon
    # Non-convex (L-shaped) field.
    l_shape = Polygon([(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)])
    assert l_shape.is_valid
    assert l_shape.area == pytest.approx(40 * 20 + 20 * 20)


def test_self_intersecting_polygon_flagged_invalid():
    shapely = pytest.importorskip("shapely.geometry")
    Polygon = shapely.Polygon
    bowtie = Polygon([(0, 0), (4, 4), (4, 0), (0, 4)])
    # A bowtie is geometrically invalid; design code must detect this rather
    # than silently producing a wrong area.
    assert bowtie.is_valid is False


def test_degenerate_polygon_zero_area():
    shapely = pytest.importorskip("shapely.geometry")
    Polygon = shapely.Polygon
    line = Polygon([(0, 0), (10, 0), (20, 0)])   # collinear -> zero area
    assert line.area == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Numerical robustness of head loss across many decades of flow
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("Q", [0.1, 1, 10, 100, 1000])
def test_headloss_monotonic_in_flow(Q):
    import math
    hi = hazen_williams_headloss(Q * 2, 110.0, 100.0, 150.0)
    lo = hazen_williams_headloss(Q, 110.0, 100.0, 150.0)
    assert hi > lo and math.isfinite(hi)
