"""S4.1 — kappa sweep figure: what the original 4-point grid could not see.

Reads the cusum_k rows of results/tables/esn_ablation.csv, plots detection / AUC /
mean lead against kappa on a log x axis, marks the shipped default (0.5), and
shades the range the paper actually swept (0.25-1.0).

Run (from repo root):
    ..\\.venv\\Scripts\\python.exe analysis\\plot_kappa.py
Writes results/figures/fig_kappa_sweep.png (does not overwrite any repo figure).
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "results" / "tables" / "esn_ablation.csv"
OUT = ROOT / "results" / "figures" / "fig_kappa_sweep.png"

# Range the paper swept; everything outside it is new information.
PAPER_RANGE = (0.25, 1.0)
DEFAULT = 0.5


def main() -> int:
    df = pd.read_csv(TABLE)
    k = df[df["param"] == "cusum_k"].sort_values("value")
    if k.empty:
        print("no cusum_k rows in", TABLE)
        return 1
    x = k["value"].to_numpy()

    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), sharex=True)
    specs = [
        ("detection_rate", "detection rate (400 failure episodes)", "#c0392b"),
        ("episode_auc", "episode AUC (threshold-free)", "#2c3e50"),
        ("mean_lead_all", "mean lead, steps/episode", "#1f77b4"),
    ]
    for ax, (col, label, color) in zip(axes, specs):
        ax.axvspan(*PAPER_RANGE, color="#d5dbdb", alpha=0.55, lw=0,
                   label="range swept in the paper")
        ax.plot(x, k[col], "o-", color=color, lw=1.8, ms=5)
        ax.axvline(DEFAULT, color="#7f8c8d", ls="--", lw=1)
        ax.set_xscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{v:g}" for v in x], fontsize=7.5, rotation=35,
                           ha="right")
        ax.minorticks_off()
        ax.set_xlabel("kappa (CUSUM drift parameter)")
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=0.25, ls=":")
        # annotate the two points that fall outside the paper's grid
        for xv in (0.05, 2.0, 5.0):
            row = k[k["value"] == xv]
            if not row.empty:
                ax.annotate(f"{row[col].iloc[0]:.3g}", (xv, row[col].iloc[0]),
                            textcoords="offset points", xytext=(0, 7),
                            ha="center", fontsize=7, color="#555555")
    axes[0].set_ylabel("value")
    axes[0].legend(loc="lower left", fontsize=7, frameon=False)
    fig.suptitle("ESN-CUSUM sensitivity to kappa: flat inside the published grid, "
                 "a cliff outside it", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170)
    print("wrote", OUT)
    print(f"\n{'kappa':>7}{'det':>9}{'lead':>8}{'fa':>8}{'auc':>9}")
    for _, r in k.iterrows():
        print(f"{r['value']:>7g}{r['detection_rate']:>9.4f}"
              f"{r['mean_lead_all']:>8.3f}{r['healthy_fa_rate']:>8.4f}"
              f"{r['episode_auc']:>9.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
