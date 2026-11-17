"""Baseline vs Model A percentage comparison figure (TA / Template 10.1 shape).

Uses only committed aggregates — no MIMIC text, no new model runs.

    python scripts/make_baseline_model_comparison_figure.py

Writes:
  docs/images/baseline_vs_model_a.png
  results/workbook2/figures/baseline_vs_model_a.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTS = [
    ROOT / "docs" / "images" / "baseline_vs_model_a.png",
    ROOT / "results" / "workbook2" / "figures" / "baseline_vs_model_a.png",
]

# Sources: docs/baseline_notes.md, docs/validation_summary.json (seed 298).
# Diagnosis panel mixes different cohorts/tasks on purpose — caption states that.
DIAGNOSIS = [
    ("Hager paper\nOASST 70B\n(2,400, diag.)", 54.9),
    ("Our baseline\nLlama 3.1 8B\n(400, diag.)", 47.4),
    ("Majority class\n(val 460)", 40.0),
    ("Model E\nTF-IDF+LR\n(val 460)", 88.7),
    ("Model A\nQwen2.5:14b\n(val 460)", 88.7),
]

# Plan metrics exist only for our models on the validation split (not Hager).
PLAN = [
    ("Checked\nacceptance\n(covered)", "Model E", 18.75),
    ("Checked\nacceptance\n(covered)", "Model A", 14.58),
    ("Joint\nsuccess\n(all 460)", "Model E", 16.30),
    ("Joint\nsuccess\n(all 460)", "Model A", 11.96),
]


def main() -> None:
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(11.2, 4.8), gridspec_kw={"width_ratios": [1.15, 1.0]})

    labels = [r[0] for r in DIAGNOSIS]
    vals = [r[1] for r in DIAGNOSIS]
    colors = ["#6b7280", "#6b7280", "#9ca3af", "#2563eb", "#059669"]
    x = np.arange(len(vals))
    bars = ax0.bar(x, vals, color=colors, width=0.72, edgecolor="white", linewidth=0.5)
    ax0.set_xticks(x)
    ax0.set_xticklabels(labels, fontsize=7.5)
    ax0.set_ylabel("Diagnostic accuracy (%)")
    ax0.set_ylim(0, 100)
    ax0.set_title("A. Diagnosis accuracy (%)", fontsize=10, loc="left")
    ax0.axhline(54.9, color="#9ca3af", ls="--", lw=0.8, alpha=0.8)
    for b, v in zip(bars, vals):
        ax0.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.1f}", ha="center", va="bottom", fontsize=8)

    metrics = ["Checked\nacceptance\n(covered)", "Joint\nsuccess\n(all 460)"]
    e_vals = [18.75, 16.30]
    a_vals = [14.58, 11.96]
    xpos = np.arange(len(metrics))
    w = 0.36
    ax1.bar(xpos - w / 2, e_vals, width=w, color="#2563eb", label="Model E")
    ax1.bar(xpos + w / 2, a_vals, width=w, color="#059669", label="Model A")
    ax1.set_xticks(xpos)
    ax1.set_xticklabels(metrics, fontsize=8)
    ax1.set_ylabel("Rate (%)")
    ax1.set_ylim(0, 40)
    ax1.set_title("B. Plan metrics on validation (not in Hager)", fontsize=10, loc="left")
    ax1.legend(fontsize=8, frameon=False)
    for i, (e, a) in enumerate(zip(e_vals, a_vals)):
        ax1.text(i - w / 2, e + 0.6, f"{e:.1f}", ha="center", fontsize=8)
        ax1.text(i + w / 2, a + 0.6, f"{a:.1f}", ha="center", fontsize=8)

    fig.suptitle(
        "Baseline vs Model A — percentages (different tasks/cohorts in panel A; see caption)",
        fontsize=10,
        y=1.02,
    )
    fig.text(
        0.5,
        -0.02,
        "Panel A: Hager = diagnosis only on Ext-CDM autonomous task; Model A/E = our validation split (460). "
        "Not like-for-like. Panel B: plan compliance (Z3 checked acceptance / joint success); Hager has no equivalent.\n"
        "Sources: docs/baseline_notes.md; docs/validation_summary.json (seed 298). R-GEN-001 / insufficient-info dominate Model A non-acceptances.",
        ha="center",
        va="top",
        fontsize=7,
        color="#374151",
    )
    fig.tight_layout()
    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=200, bbox_inches="tight")
        print("wrote", out)
    plt.close(fig)


if __name__ == "__main__":
    main()
