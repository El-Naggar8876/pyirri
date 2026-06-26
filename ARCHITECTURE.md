# OpenIrri software architecture & engineering notes

This document complements the SoftwareX article (Section 2.1) and answers the
software-engineering questions raised in peer review: modular design, the single
source of truth for engineering formulas, exception handling, numerical
convergence, and testing/CI.

## Layered, modular design

OpenIrri is organised in three layers:

1. **Presentation layer** — `app.py` plus the per-module `show()` entry points.
   Routing is sidebar-driven; each module reads and writes a namespaced key in
   `st.session_state`, so downstream modules consume upstream results without
   global coupling.
2. **Engineering computation layer** — domain modules in `modules/`
   (`crop_water_requirements`, `sprinkler_selection`, `operational_design`,
   `pipe_network_layout`, `pipe_network_design`, `hydraulic_design`,
   `pump_selection`, `pump_math_utils`, `cost_estimation`, `field_layout_manager`).
3. **Shared services layer** — `components/` (validators, export utilities,
   logging, toasts, icons) and `config/` (theme, runtime configuration).

## Single source of truth for formulas

The core numerical kernels (Hazen-Williams head loss, Christiansen F-factor and
uniformity coefficient, total dynamic head, hydraulic/brake/motor power, NPSH
margin, velocity, and the velocity-constrained pipe-diameter selector) live in
`modules/engineering_kernels.py`. This module imports only the standard library,
so it is unit-testable in CI without a Streamlit runtime. The GUI modules
delegate to it — e.g. `pipe_network_design.calculate_hazen_williams()` now calls
`engineering_kernels.hazen_williams_headloss()` — guaranteeing that what the
tests verify is exactly what the application runs.

## Numerical convergence & iteration

Pipe sizing is a **deterministic, bounded** search, not an open-ended loop:
`select_pipe_diameter()` scans the ordered list of standard pipe diameters and
returns the smallest pipe whose mean velocity satisfies the economic-velocity
cap (default <= 2.0 m/s). If no standard pipe satisfies the cap (e.g. an
extreme flow), the largest available pipe is returned with `converged=False`
so the caller surfaces a warning instead of failing silently or looping. The
20 % lateral-pressure-variation criterion (Keller & Bliesner) is checked by
`lateral_pressure_variation_ok()`. Both behaviours are covered in
`tests/test_edge_cases.py`.

## Exception handling

* Degenerate hydraulic input (zero/negative flow, zero diameter) returns 0.0
  rather than raising or producing NaN/Inf (`hazen_williams_headloss`).
* Empty catch-can samples raise an explicit `ValueError`; a zero mean returns a
  defined `CU = 0` (`christiansen_uniformity`).
* Non-positive pump or motor efficiency returns 0 power instead of dividing by
  zero (`brake_power_kw`, `motor_power_kw`).
* Optional Google Earth Engine credentials are wrapped so a missing/invalid key
  falls back to manual climate entry and local JSON project storage rather than
  aborting the session.
* Field geometry is validated with Shapely (`is_valid`); self-intersecting or
  degenerate (zero-area) polygons are detected before any area-dependent design
  step.

## Testing & continuous integration

* `tests/` — `pytest` regression and edge-case suite (extreme wind de-rating of
  uniformity, irregular/self-intersecting field polygons, pipe-sizing
  convergence, head-loss monotonicity).
* `validation/hydraulic_benchmark.py` — cross-checks the head-loss engine and
  the Christiansen F-factor against an independent hand calculation **and the
  official US-EPA EPANET 2.2 solver** (via the WNTR package). Agreement is
  better than 0.3 %.
* `.github/workflows/ci.yml` — runs the test suite (with coverage) and the
  EPANET benchmark on Python 3.11 and 3.12 for every push and pull request.

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ --cov=modules
python validation/hydraulic_benchmark.py
```
