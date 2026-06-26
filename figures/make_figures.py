"""
Reproducible generation of the PyIrri engineering figures used in the SoftwareX
article. Driven by the actual engineering kernels (modules/engineering_kernels.py)
and pump-curve solver (modules/pump_math_utils.py) with the Section-4 wheat
case-study parameters.

    python figures/make_figures.py
Outputs 300-dpi PNG + vector PDF for each figure into figures/.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

from modules.engineering_kernels import hazen_williams_headloss, lateral_headloss
from modules.pump_math_utils import PumpCurveSolver

OUT = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans", "axes.grid": True,
                     "grid.alpha": 0.3, "savefig.dpi": 300})
NAVY, BLUE, ORANGE, RED, GREEN = "#1F3864", "#2E86AB", "#F18F01", "#C0392B", "#2E7D32"

def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)
    print("wrote", name + ".png /.pdf")

# --------------------------------------------------------------------------- #
# Figure 1 — architecture / workflow diagram
# --------------------------------------------------------------------------- #
def fig_architecture():
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_xlim(0, 100); ax.set_ylim(0, 70); ax.axis("off")

    def box(x, y, w, h, text, fc, ec=NAVY, fs=9, tc="black"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                    fc=fc, ec=ec, lw=1.3))
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, color=tc, wrap=True)

    def band(y, h, label, color):
        ax.add_patch(FancyBboxPatch((1, y), 98, h, boxstyle="round,pad=0.2,rounding_size=1",
                                    fc=color, ec="none", alpha=0.12))
        ax.text(2.5, y + h - 2.2, label, ha="left", va="top", fontsize=10, color=NAVY, fontweight="bold")

    # Presentation layer
    band(56, 12, "Presentation layer (Streamlit)", BLUE)
    box(33, 58.5, 34, 6.5, "app.py  —  sidebar router & session_state store", "#D6E4F0", fs=9)

    # Engineering pipeline
    band(20, 33, "Engineering computation layer  (modules/)", ORANGE)
    stages = ["Crop Water\nRequirements", "Sprinkler\nSelection", "Operational\nDesign",
              "Field /\nPipe Layout", "Hydraulic\nDesign", "Pump\nSelection",
              "Cost\nEstimation", "Reports\n(PDF / Excel)"]
    x0, w, gap, y = 3.5, 10.5, 1.5, 39
    centers = []
    for i, s in enumerate(stages):
        x = x0 + i*(w+gap)
        box(x, y, w, 8.5, s, "#FBE7C6", ec=ORANGE, fs=8)
        centers.append(x + w/2)
        if i:  # arrow from previous
            ax.add_patch(FancyArrowPatch((centers[i-1]+w/2, y+4.25), (x, y+4.25),
                         arrowstyle="-|>", mutation_scale=12, color=NAVY, lw=1.3))
    ax.text(50, 34.5, "single reactive pipeline — each stage consumes the previous stage's results",
            ha="center", fontsize=8.5, style="italic", color=NAVY)
    # shared kernel
    box(28, 22, 44, 6, "engineering_kernels.py  —  single source-of-truth formulas\n(Hazen-Williams · Christiansen · TDH · power · NPSH)",
        "#FDF2D0", ec=ORANGE, fs=8)

    # Services + optional GEE
    band(3, 14, "Shared services & configuration", GREEN)
    for i, (t) in enumerate(["validators", "export\n(PDF/XLSX/DXF)", "logging", "theme / config",
                             "tests/ + CI", "JSON project\nsnapshots"]):
        box(3.5 + i*15.8, 5.5, 14, 7, t, "#D9EAD3", ec=GREEN, fs=8)

    # optional GEE callout
    ax.add_patch(FancyBboxPatch((70, 58.5), 28, 6.5, boxstyle="round,pad=0.3,rounding_size=1.2",
                 fc="#EDE7F6", ec="#5E35B1", lw=1.2, linestyle="--"))
    ax.text(84, 61.7, "Optional Google Earth Engine\n(climate + DEM, cloud snapshots) — offline-capable",
            ha="center", va="center", fontsize=7.5, color="#4527A0")

    ax.set_title("Figure 1.  PyIrri software architecture and design workflow",
                 fontsize=12, color=NAVY, fontweight="bold", pad=10)
    save(fig, "Fig1_architecture")

# --------------------------------------------------------------------------- #
# Figure (pump) — Q-H, efficiency and system curve with duty point
# --------------------------------------------------------------------------- #
def fig_pump():
    """Pump H(Q), efficiency and system curve with the duty point at the
    confirmed 182 m3/h peak simultaneous demand (5 subplots x 36.4 m3/h).
    Curves are illustrative of the pump-selection module output; the actual
    pump/curve must be taken from a re-run of pump selection at 182 m3/h."""
    duty_q, duty_head = 182.0, 85.0          # confirmed peak flow; representative TDH
    Qbep, Hbep, eta_bep, Qmax = 200.0, 80.0, 78.0, 300.0
    # quadratic pump curve through BEP (200,80) and duty (182,85)
    a = (Hbep - duty_head) / (duty_q**2 - Qbep**2)
    H0 = duty_head + a * duty_q**2
    q = np.linspace(0, Qmax, 200)
    H = H0 - a * q**2
    eta = np.clip(eta_bep * (2*(q/Qbep) - (q/Qbep)**2), 0, None)
    static = 45.0
    k = (duty_head - static) / (duty_q ** 1.852)
    h_sys = static + k * (q ** 1.852)
    duty_eta = eta_bep * (2*(duty_q/Qbep) - (duty_q/Qbep)**2)

    fig, ax1 = plt.subplots(figsize=(8.2, 5.4))
    ax1.plot(q, H, color=BLUE, lw=2.4, label="Pump head curve  H(Q)")
    ax1.plot(q, h_sys, color=ORANGE, lw=2.4, ls="--",
             label="System curve  H = H$_{stat}$ + kQ$^{1.852}$")
    ax1.plot(duty_q, duty_head, "o", color=RED, ms=10, zorder=6)
    ax1.annotate(f"Duty point\n{duty_q:.0f} m$^3$/h, {duty_head:.0f} m",
                 (duty_q, duty_head), xytext=(duty_q-150, duty_head+8),
                 fontsize=9, color=RED, arrowprops=dict(arrowstyle="->", color=RED))
    ax1.set_xlabel("Flow rate Q (m$^3$/h)"); ax1.set_ylabel("Head H (m)", color=BLUE)
    ax1.tick_params(axis="y", labelcolor=BLUE)
    ax1.set_xlim(0, Qmax); ax1.set_ylim(0, max(H0, 110))

    ax2 = ax1.twinx(); ax2.grid(False)
    ax2.plot(q, eta, color=GREEN, lw=2.0, ls=":", label="Efficiency $\\eta$(Q)")
    ax2.plot(duty_q, duty_eta, "s", color=GREEN, ms=8)
    ax2.annotate(f"$\\eta$ \u2248 {duty_eta:.0f}%", (duty_q, duty_eta),
                 xytext=(duty_q+8, duty_eta-10), fontsize=9, color=GREEN)
    ax2.set_ylabel("Efficiency $\\eta$ (%)", color=GREEN); ax2.tick_params(axis="y", labelcolor=GREEN)
    ax2.set_ylim(0, 100)

    l1, la1 = ax1.get_legend_handles_labels(); l2, la2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, la1 + la2, loc="lower center", fontsize=8.5, framealpha=0.92)
    ax1.set_title("Pump head\u2013flow and system curves, duty at the 182 m$^3$/h peak\n"
                  "(illustrative; finalise from a pump-selection re-run at 182 m$^3$/h)",
                  fontsize=10.5, color=NAVY)
    save(fig, "Fig_pump_QH_system_curve")

# --------------------------------------------------------------------------- #
# Figure (hydraulics) — cumulative head-loss profile, worst-case circuit
# --------------------------------------------------------------------------- #
def fig_headloss():
    # Worst-case circuit geometry from the case study (C = 150 PVC).
    main_L, main_D, main_Q = 270.0, 176.0, 182.0          # DN200
    sub_L, sub_D, sub_Q = 177.0, 140.8, 91.0              # DN160
    lat_L, lat_D, lat_Q, lat_n = 403.2, 66.0, 16.64, 32   # DN75 lateral, 32 outlets

    hf_main = hazen_williams_headloss(main_Q, main_D, main_L, 150)
    hf_sub = hazen_williams_headloss(sub_Q, sub_D, sub_L, 150)
    hf_lat = lateral_headloss(lat_Q, lat_D, lat_L, lat_n, 150)

    xs = [0, main_L, main_L+sub_L, main_L+sub_L+lat_L]
    cum = [0, hf_main, hf_main+hf_sub, hf_main+hf_sub+hf_lat]
    labels = ["Pump /\nsource", f"Mainline\nDN200\n{hf_main:.2f} m",
              f"Submain\nDN160\n{hf_sub:.2f} m", f"Lateral end\nDN75 (F-factor)\n{hf_lat:.2f} m"]

    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    ax.plot(xs, cum, "-o", color=BLUE, lw=2.3, ms=8)
    ax.fill_between(xs, cum, color=BLUE, alpha=0.08)
    for x, y, lab in zip(xs, cum, labels):
        ax.annotate(lab, (x, y), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=8.3, color=NAVY)
    ax.set_xlabel("Distance along worst-case circuit (m)")
    ax.set_ylabel("Cumulative friction head loss (m)")
    ax.set_title(f"Hydraulic head-loss profile along the worst-case circuit\n"
                 f"(Hazen-Williams C = 150; total ≈ {cum[-1]:.2f} m)",
                 fontsize=10.5, color=NAVY)
    ax.set_ylim(0, cum[-1]*1.35); ax.set_xlim(-20, xs[-1]+40)
    save(fig, "Fig_headloss_profile")

if __name__ == "__main__":
    fig_pump(); fig_headloss()  # Fig 1 architecture kept as author original
    print("All figures written to", OUT)
