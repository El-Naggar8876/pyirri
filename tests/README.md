# OpenIrri test suite

Deterministic regression and edge-case tests for the OpenIrri engineering kernels.

```bash
pip install -r ../requirements-dev.txt
pytest                      # run all tests
pytest --cov=modules        # with coverage
python ../validation/hydraulic_benchmark.py   # EPANET 2.2 cross-check
```

| File | Scope |
|------|-------|
| `test_hydraulics.py` | Hazen-Williams head loss, Christiansen F-factor & uniformity, velocity, 20 % lateral-pressure rule. Values re-derived from closed form. |
| `test_pump.py` | Total dynamic head, hydraulic/brake/motor power, NPSH margin, pump-curve solver duty point. |
| `test_edge_cases.py` | Extreme wind de-rating of CU, irregular/self-intersecting/degenerate field polygons, deterministic convergence of the pipe-diameter selection loop, monotonicity of head loss over five decades of flow. |

All kernels under test live in `modules/engineering_kernels.py`, which the
Streamlit GUI modules delegate to (single source of truth). The hydraulic
results are additionally cross-checked against the official EPANET 2.2 solver in
`validation/hydraulic_benchmark.py`.
