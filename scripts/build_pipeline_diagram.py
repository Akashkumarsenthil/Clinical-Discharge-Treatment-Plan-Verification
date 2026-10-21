"""Draw the data pipeline diagram used in the README.

Run from the repository root:   python scripts/build_pipeline_diagram.py
Output: docs/images/data_pipeline.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("1  Download + check", "SHA256: MIMIC-IV 33/33\nExt-CDM 12/12 files"),
    ("2  Link check", "2,400 of 2,400 cases\nfound in MIMIC-IV"),
    ("3  Cleaning", "75 duplicate rows\nremoved"),
    ("4  Missing values", "rule per column;\nlab values parsed"),
    ("5  Validation", "passes; fails on a\ncorrupted copy"),
    ("6  Exploration (EDA)", "statistics, plots,\ncomputed findings"),
    ("7  Fixed splits", "1,840 / 460 / 100\n+ leakage test"),
]
W, H, GAP = 2.6, 1.25, 0.4
POS = [(i * (W + GAP), 1.9) for i in range(4)] + [(i * (W + GAP), 0.0) for i in range(3)]

fig, ax = plt.subplots(figsize=(10.5, 4.3))
for (title, sub), (x, y) in zip(STEPS, POS):
    ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.03,rounding_size=0.08", fc="#dae3f3", ec="#4472c4", lw=1.4))
    ax.text(x + W / 2, y + H * 0.68, title, ha="center", va="center", fontsize=10, fontweight="bold")
    ax.text(x + W / 2, y + H * 0.28, sub, ha="center", va="center", fontsize=9)
def arrow(a, b, **kw):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, color="#444", lw=1.4, **kw))
for i in (0, 1, 2):
    x, y = POS[i]; arrow((x + W + 0.03, y + H / 2), (x + W + GAP - 0.03, y + H / 2))
for i in (4, 5):
    x, y = POS[i]; arrow((x + W + 0.03, y + H / 2), (x + W + GAP - 0.03, y + H / 2))
x3, y3 = POS[3]; x4, y4 = POS[4]
ymid = y3 - 0.35                       # elbow: down from step 4, left, down into step 5
ax.plot([x3 + W / 2, x3 + W / 2, x4 + W / 2], [y3 - 0.03, ymid, ymid], color="#444", lw=1.4, solid_capstyle="butt")
arrow((x4 + W / 2, ymid), (x4 + W / 2, y4 + H + 0.03))
ax.set_xlim(-0.2, 4 * W + 3 * GAP + 0.2); ax.set_ylim(-0.25, 3.35); ax.axis("off")
fig.text(0.01, 0.01, "Produced by scripts/build_pipeline_diagram.py", fontsize=7, color="#666")
out = ROOT / "docs" / "images" / "data_pipeline.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=170, bbox_inches="tight")
print("saved", out)
