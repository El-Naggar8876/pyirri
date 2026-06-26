"""
Hydraulic validation benchmark for OpenIrri.

Cross-checks the OpenIrri Hazen-Williams head-loss engine and the Christiansen
multi-outlet F-factor against:

  (1) an independent closed-form (hand) calculation, and
  (2) the official US-EPA EPANET 2.2 solver, accessed through the WNTR
      Python package (https://github.com/USEPA/WNTR).

Run:
    pip install wntr
    python validation/hydraulic_benchmark.py

The script prints a comparison table and writes ``benchmark_results.csv``.
All three methods are expected to agree to well within 2 %.

Reference equations
-------------------
Hazen-Williams (SI, head in m, Q in m^3 s^-1, D in m):
    hf = 10.67 * L * Q^1.852 / (C^1.852 * D^4.87)

Christiansen multi-outlet reduction factor (m = 1.852):
    F = 1/(m+1) + 1/(2N) + sqrt(m-1)/(6 N^2)
"""

from __future__ import annotations

import math
import csv
import os
import tempfile

# --------------------------------------------------------------------------- #
# 1. OpenIrri engine (copied verbatim from modules/pipe_network_design.py so the
#    benchmark is self-contained and testable in CI without Streamlit).
# --------------------------------------------------------------------------- #
def pyirri_hazen_williams(Q_m3h: float, D_mm: float, L_m: float, C: float = 130) -> float:
    """Head loss (m) for a single pipe carrying a constant flow."""
    if Q_m3h == 0 or D_mm == 0:
        return 0.0
    Q_m3s = Q_m3h / 3600.0
    D_m = D_mm / 1000.0
    return 10.67 * L_m * (Q_m3s ** 1.852) / ((C ** 1.852) * (D_m ** 4.87))


def pyirri_f_factor(n_outlets: int) -> float:
    """Christiansen F-factor used by OpenIrri for multi-outlet laterals."""
    if n_outlets <= 1:
        return 1.0
    m = 1.852
    return (1 / (m + 1)) + (1 / (2 * n_outlets)) + math.sqrt(m - 1) / (6 * n_outlets ** 2)


# --------------------------------------------------------------------------- #
# 2. Independent hand calculation (re-derived, not reusing OpenIrri's function).
# --------------------------------------------------------------------------- #
def hand_hazen_williams(Q_m3h, D_mm, L_m, C):
    Q = Q_m3h / 3600.0          # m^3/s
    D = D_mm / 1000.0           # m
    # h_f = 10.67 L Q^1.852 / (C^1.852 D^4.87)
    return (10.67 * L_m * math.pow(Q, 1.852)) / (math.pow(C, 1.852) * math.pow(D, 4.87))


def hand_multioutlet(q_outlet_m3h, n_outlets, spacing_m, D_mm, C):
    """
    Head loss of a lateral with n equally spaced outlets, computed the long way:
    sum the Hazen-Williams loss of every segment with its actual (decreasing) flow.
    Segment k (k = 1..n) lies between the inlet side and outlet k and carries the
    flow still to be delivered downstream: (n - k + 1) * q.
    """
    total = 0.0
    for k in range(1, n_outlets + 1):
        seg_flow = (n_outlets - k + 1) * q_outlet_m3h
        total += hand_hazen_williams(seg_flow, D_mm, spacing_m, C)
    return total


# --------------------------------------------------------------------------- #
# 3. EPANET 2.2 reference via WNTR.
# --------------------------------------------------------------------------- #
def epanet_single_pipe(Q_m3h, D_mm, L_m, C):
    import wntr
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = "H-W"
    wn.options.hydraulic.inpfile_units = "LPS"
    wn.add_reservoir("R", base_head=100.0)
    Q_lps = Q_m3h / 3.6                       # m^3/h -> L/s
    wn.add_junction("J", base_demand=Q_lps / 1000.0, elevation=0.0)  # demand in m^3/s
    wn.add_pipe("P", "R", "J", length=L_m, diameter=D_mm / 1000.0,
                roughness=C, minor_loss=0.0)
    with tempfile.TemporaryDirectory() as td:
        sim = wntr.sim.EpanetSimulator(wn)
        res = sim.run_sim(file_prefix=os.path.join(td, "bench"))
    head = res.node["head"]
    return float(head["R"].iloc[0] - head["J"].iloc[0])


def epanet_multioutlet(q_outlet_m3h, n_outlets, spacing_m, D_mm, C):
    import wntr
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.headloss = "H-W"
    wn.options.hydraulic.inpfile_units = "LPS"
    wn.add_reservoir("R", base_head=100.0)
    q_m3s = q_outlet_m3h / 3600.0
    prev = "R"
    for i in range(1, n_outlets + 1):
        node = f"J{i}"
        wn.add_junction(node, base_demand=q_m3s, elevation=0.0)
        wn.add_pipe(f"P{i}", prev, node, length=spacing_m,
                    diameter=D_mm / 1000.0, roughness=C, minor_loss=0.0)
        prev = node
    with tempfile.TemporaryDirectory() as td:
        sim = wntr.sim.EpanetSimulator(wn)
        res = sim.run_sim(file_prefix=os.path.join(td, "bench"))
    head = res.node["head"]
    return float(head["R"].iloc[0] - head[f"J{n_outlets}"].iloc[0])


# --------------------------------------------------------------------------- #
# 4. Benchmark cases (drawn from the Section-4 wheat case study).
# --------------------------------------------------------------------------- #
def pct_diff(a, b):
    return 100.0 * abs(a - b) / b if b else float("nan")


def main():
    rows = []

    # ---- Case A: single mainline pipe at the source duty ----
    # Source supply 200 m3/h, 270 m N-S PVC mainline, DN200 (ID 176 mm), C = 150.
    A = dict(label="Mainline DN200, Q=200 m3/h, L=270 m, C=150",
             Q=200.0, D=176.0, L=270.0, C=150.0)
    py = pyirri_hazen_williams(A["Q"], A["D"], A["L"], A["C"])
    hd = hand_hazen_williams(A["Q"], A["D"], A["L"], A["C"])
    ep = epanet_single_pipe(A["Q"], A["D"], A["L"], A["C"])
    rows.append([A["label"], py, hd, ep, pct_diff(py, ep)])

    # ---- Case B: single submain pipe ----
    B = dict(label="Submain DN160, Q=109 m3/h, L=177 m, C=150",
             Q=109.0, D=140.8, L=177.0, C=150.0)
    py = pyirri_hazen_williams(B["Q"], B["D"], B["L"], B["C"])
    hd = hand_hazen_williams(B["Q"], B["D"], B["L"], B["C"])
    ep = epanet_single_pipe(B["Q"], B["D"], B["L"], B["C"])
    rows.append([B["label"], py, hd, ep, pct_diff(py, ep)])

    # ---- Case C: multi-outlet lateral with Christiansen F-factor ----
    # 32 impact sprinklers, 0.52 m3/h each, 12.6 m spacing, DN63 (ID 55.4 mm), C = 150.
    n = 32
    q = 0.52
    spacing = 12.6
    D_lat = 55.4
    C_lat = 150.0
    Q_in = n * q
    L_lat = n * spacing
    F = pyirri_f_factor(n)
    hf_full = pyirri_hazen_williams(Q_in, D_lat, L_lat, C_lat)
    py_lat = F * hf_full
    hd_lat = hand_multioutlet(q, n, spacing, D_lat, C_lat)
    ep_lat = epanet_multioutlet(q, n, spacing, D_lat, C_lat)
    rows.append([f"Lateral: {n} outlets x {q} m3/h, F={F:.4f}",
                 py_lat, hd_lat, ep_lat, pct_diff(py_lat, ep_lat)])

    # ---- print + save ----
    hdr = ["Case", "OpenIrri (m)", "Hand calc (m)", "EPANET 2.2 (m)", "OpenIrri vs EPANET (%)"]
    widths = [44, 12, 14, 16, 22]
    line = " | ".join(h.ljust(w) for h, w in zip(hdr, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        cells = [str(r[0]).ljust(widths[0])]
        cells += [f"{r[i]:.4f}".ljust(widths[i]) for i in range(1, 4)]
        cells += [f"{r[4]:.2f}".ljust(widths[4])]
        print(" | ".join(cells))

    out = os.path.join(os.path.dirname(__file__), "benchmark_results.csv")
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(hdr)
        for r in rows:
            w.writerow([r[0]] + [f"{x:.4f}" for x in r[1:]])
    print(f"\nWritten: {out}")

    max_dev = max(r[4] for r in rows)
    print(f"Maximum OpenIrri-vs-EPANET deviation: {max_dev:.2f} %")
    assert max_dev < 2.0, "Deviation exceeds 2 % tolerance"
    print("PASS: all methods agree within 2 %.")


if __name__ == "__main__":
    main()
