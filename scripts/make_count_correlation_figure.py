"""Draw the correlation heatmap of the per-case counts (Workbook 2, section 3.6).

Uses the cleaned and transformed Ext-CDM tables (cases_master). Writes counts and coefficients only, no patient text.

    python scripts/make_count_correlation_figure.py     # needs MIMIC_DIR with the real data
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.data import ext_cdm as E  # noqa: E402

COLUMNS = {
    "hpi_words": "History length (words)",
    "n_laboratory_tests": "Lab rows",
    "n_radiology_reports": "Radiology reports",
    "n_icd_diagnosis": "ICD diagnoses",
}
OUT = ROOT / "results" / "workbook2" / "figures" / "3_6g_count_correlation.png"


def main() -> None:
    cleaned, _ = E.clean_tables(E.load_tables())
    master = E.transform_tables(cleaned)["cases_master"]
    corr = master[list(COLUMNS)].astype(float).corr(method="pearson")
    labels = list(COLUMNS.values())
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=9, rotation=20, ha="right")
    ax.set_yticks(range(4))
    ax.set_yticklabels(labels, fontsize=9)
    for i in range(4):
        for j in range(4):
            v = corr.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="white" if abs(v) > 0.55 else "black", fontsize=11)
    ax.set_title(f"Correlation of per-case counts (Pearson r, n = {len(master):,} cases)", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Pearson r")
    fig.subplots_adjust(left=0.27, right=0.84, bottom=0.22, top=0.92)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(OUT, dpi=200)
    print(corr.round(2).to_string())
    print("wrote", OUT)


if __name__ == "__main__":
    main()
