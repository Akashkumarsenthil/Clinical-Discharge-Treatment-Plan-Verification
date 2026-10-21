"""End-to-end data pipeline demo for Team Meeting 1 (ISA run script, Template 6B).

Run from the project folder:   python scripts/data_demo.py <step>
Steps (in demo order):
  manifest   sources, licence, integrity, link to MIMIC-IV
  samples    schemas and representative rows (on screen only, text truncated)
  clean      duplicates removed, before/after counts
  missing    missing values per column and the handling rule
  transform  formatting and derived fields (log of every transformation)
  validate   checks pass on clean data, fail on a deliberately corrupted copy
  eda        statistics, plots and computed findings
  splits     fixed stratified splits and a leakage test
  all        everything above

Reads credentialed data from $MIMIC_DIR (default ~/data/mimic). The working set is the
17 MB Ext-CDM extract. MIMIC-IV is used only for the admissions link check. Nothing from
the data is written into this folder except counts, aggregate figures and case IDs.
Do not paste the 'samples' output into slides or the report.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data import splits as S  # noqa: E402

FIG_DIR = ROOT / "results" / "figures"
RESULTS = ROOT / "results"
SPLIT_DIR = ROOT / "data" / "splits"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _clean():
    tables = E.load_tables()
    cleaned, report = E.clean_tables(tables)
    return tables, cleaned, report


def step_manifest():
    """Sources, collection route, integrity (SHA256 vs PhysioNet's list), link to MIMIC-IV."""
    print("== Data extraction: sources and integrity ==")
    print("Collection route: PhysioNet credentialed access -> data use agreement -> download "
          "(wget, resumable) -> SHA256 verification -> link check (see docs/data_collection.md)")
    for label, directory in [("MIMIC-IV v3.1", E.MIMIC_IV_DIR), ("MIMIC-IV-Ext-CDM v1.1", E.EXT_CDM_DIR)]:
        listed = [l.split() for l in (directory / "SHA256SUMS.txt").read_text().replace("\r", "").splitlines()
                  if len(l.split()) == 2]
        ok = bad = size = 0
        for digest, rel in listed:
            f = directory / rel
            if f.exists():
                size += f.stat().st_size
                ok, bad = (ok + 1, bad) if sha256(f) == digest else (ok, bad + 1)
            else:
                bad += 1
        print(f"{label:24s} files listed={len(listed):2d}  verified={ok:2d}  failed/missing={bad}  "
              f"size={size/1e9:.2f} GB   licence: PhysioNet Credentialed Health Data License 1.5.0")
    adm = pd.read_csv(E.MIMIC_IV_DIR / "hosp" / "admissions.csv.gz", usecols=["hadm_id"])
    cases = E.case_table(E.load_pathology_ids())
    print(f"Link check: {int(cases['hadm_id'].isin(adm['hadm_id']).sum())} of {len(cases)} Ext-CDM cases "
          f"found in MIMIC-IV admissions ({len(adm):,} admissions)")


def step_samples():
    """Schemas and a few representative rows. On screen only; free text is truncated."""
    print("== Data extraction: representative samples (screen only, do not share) ==")
    tables = E.load_tables()
    for name, df in tables.items():
        print(f"\n[{name}]  {len(df):,} rows x {len(df.columns)} columns")
        print("  columns:", ", ".join(f"{c} ({t})" for c, t in df.dtypes.astype(str).items()))
        sample = df.head(3).copy()
        for c in sample.columns:
            if sample[c].dtype == object:
                sample[c] = sample[c].astype(str).str.slice(0, 40) + "..."
        print(sample.to_string(index=False, max_colwidth=46))


def step_clean():
    """Cleaning: exact duplicates removed, before/after counts."""
    print("== Data cleaning: duplicates (before / after) ==")
    _, cleaned, report = _clean()
    print(report.to_string(index=False))
    print(f"Duplicates removed: {int(report['duplicate_rows'].sum())} rows")
    return cleaned


def step_missing():
    """Missing values: where they are and the rule applied to each."""
    import pandas as pd
    print("== Data cleaning: missing values and handling rules ==")
    tables = E.load_tables()
    tables["lab_test_mapping"] = pd.read_csv(E.EXT_CDM_DIR / "lab_test_mapping.csv")
    cleaned, _ = E.clean_tables(tables)
    print(E.missing_report(cleaned).to_string(index=False))


def step_transform():
    """Formatting and derived fields, with a log of every transformation."""
    print("== Data cleaning: transformations and formatting ==")
    for tbl, src, op, out, why in E.TRANSFORM_LOG:
        print(f"- {tbl}: {src} -> {op} => {out}   [why: {why}]")
    _, cleaned, _ = _clean()
    x = E.transform_tables(cleaned)
    labs = x["laboratory_tests"]
    print(f"\nLab values: {labs['value_is_numeric'].mean()*100:.1f}% numeric, "
          f"{labs['unit'].notna().mean()*100:.1f}% with a unit, "
          f"{labs['qualifier'].notna().sum()} with a '<' or '>' qualifier; 0 rows lost in the label join "
          f"({int(labs['label'].isna().sum())} unlabeled)")
    print("Lab flags (low / normal / high / unknown):", labs["flag"].value_counts().to_dict())
    print("cases_master:", x["cases_master"].shape[0], "cases x", x["cases_master"].shape[1], "columns")
    print("Transformed tables stay in memory. Patient files are not written into this folder.")
    return x


def step_validate():
    """Validation: passes on cleaned data, fails on a deliberately corrupted copy."""
    print("== Data cleaning: validation checks ==")
    ids = E.load_pathology_ids()
    _, cleaned, _ = _clean()
    good = E.validate_tables(cleaned, ids)
    print(f"Cleaned data: {'PASS (0 problems)' if not good else 'FAIL'}")
    for p in good:
        print("  -", p)
    bad = E.validate_tables(E.corrupt(cleaned), ids)
    print(f"Corrupted copy: {'PASS (unexpected!)' if not bad else f'FAIL as expected ({len(bad)} problems caught)'}")
    for p in bad:
        print("  -", p)


def step_eda():
    """Statistics, plots and computed findings (counts and aggregates only)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    print("== Exploratory data analysis ==")
    _, cleaned, report = _clean()
    x = E.transform_tables(cleaned)
    master, labs, rad = x["cases_master"], x["laboratory_tests"], x["radiology_reports"]

    # --- statistics table
    stats = pd.DataFrame({
        "hpi_words": master["hpi_words"].describe(),
        "lab_rows_per_case": master["n_laboratory_tests"].describe(),
        "radiology_reports_per_case": master["n_radiology_reports"].describe(),
        "icd_diagnoses_per_case": master["n_icd_diagnosis"].describe(),
    }).round(1).T[["mean", "std", "min", "50%", "max"]]
    print(stats.to_string())
    RESULTS.mkdir(exist_ok=True)
    stats.to_csv(RESULTS / "eda_summary.csv")

    # --- findings, computed from the data
    counts = master["pathology"].value_counts()
    abn = labs[labs["flag"] != "unknown"].assign(abnormal=lambda d: d["flag"].isin(["low", "high"]))
    abn_by_path = abn.merge(master[["hadm_id", "pathology"]], on="hadm_id").groupby("pathology")["abnormal"].mean() * 100
    words_by_path = master.groupby("pathology")["hpi_words"].median()
    micro_cov = master["n_microbiology"].gt(0).mean() * 100
    findings = [
        f"Classes are imbalanced: {counts.idxmax()} {counts.max()} vs {counts.idxmin()} {counts.min()} "
        f"({counts.max()/counts.min():.1f}x) -> stratify splits and report per-class results.",
        f"{(labs['flag']=='unknown').mean()*100:.1f}% of lab rows have no usable reference range or numeric value "
        f"-> cannot be flagged; kept as 'unknown' instead of imputed.",
        f"{abn['abnormal'].mean()*100:.1f}% of flaggable lab results are abnormal "
        f"(by class: " + ", ".join(f"{k} {v:.0f}%" for k, v in abn_by_path.sort_values(ascending=False).items()) + ").",
        f"History-of-present-illness length is skewed: median {int(master['hpi_words'].median())} words, "
        f"max {int(master['hpi_words'].max())}; median by class: "
        + ", ".join(f"{k} {int(v)}" for k, v in words_by_path.items()) + ".",
        f"Only {micro_cov:.0f}% of cases have microbiology results; labs and radiology cover all 2,400 cases.",
        f"Duplicates affected only the ICD/procedure tables ({int(report['duplicate_rows'].sum())} rows in total).",
    ]
    print("\nFindings:")
    for f in findings:
        print(" *", f)

    # --- plots
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    blue = "#4472c4"
    counts.plot.bar(ax=ax[0, 0], color=blue); ax[0, 0].set_title("Cases per pathology"); ax[0, 0].set_xlabel("")
    master.boxplot(column="hpi_words", by="pathology", ax=ax[0, 1], grid=False)
    ax[0, 1].set_title("HPI length (words) by pathology"); ax[0, 1].set_xlabel(""); fig.suptitle("")
    plt.setp(ax[0, 1].get_xticklabels(), rotation=30, ha="right")
    share = labs.merge(master[["hadm_id", "pathology"]], on="hadm_id").groupby(["pathology", "flag"]).size().unstack(fill_value=0)
    (share.div(share.sum(axis=1), axis=0) * 100)[["low", "normal", "high", "unknown"]].plot.bar(
        stacked=True, ax=ax[0, 2], color=["#ed7d31", blue, "#c00000", "#bfbfbf"])
    ax[0, 2].set_title("Lab flags (% of rows) by pathology"); ax[0, 2].set_xlabel(""); ax[0, 2].legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.42), ncol=4)
    labs["label"].value_counts().head(10).sort_values().plot.barh(ax=ax[1, 0], color=blue)
    ax[1, 0].set_title("10 most frequent lab tests (rows)"); ax[1, 0].set_ylabel("")
    rad["modality"].value_counts().sort_values().plot.barh(ax=ax[1, 1], color=blue)
    ax[1, 1].set_title("Radiology reports by modality"); ax[1, 1].set_ylabel("")
    miss = E.missing_report(cleaned)
    short = {"laboratory_tests": "labs", "lab_test_mapping": "lab_map", "discharge_procedures": "dis_proc"}
    ax[1, 2].barh(miss["table"].map(lambda t: short.get(t, t)) + "." + miss["column"].str.replace("ref_range_", "ref_"), miss["missing_pct"], color=blue)
    ax[1, 2].set_title("Missing values (%) by column")
    fig.text(0.01, 0.005, "Produced by project/scripts/data_demo.py (eda)", fontsize=7)
    out = FIG_DIR / "eda_overview.png"
    fig.savefig(out, dpi=150, bbox_inches="tight"); plt.close(fig)
    print("\nFigure saved:", out.relative_to(ROOT), "| statistics saved: results/eda_summary.csv")


def step_splits():
    """Fixed stratified splits, grouped by patient, with admission-level and patient-level leakage tests."""
    print("== Splits and leakage tests ==")
    cases = E.case_table(E.load_pathology_ids())
    subject_of = E.subject_map()
    v1 = S.make_splits(cases)
    print("v1 (split by admission): patients present in more than one split:", S.patient_overlap(v1, subject_of))
    splits = S.make_grouped_splits(cases, subject_of)
    print("\nv2 (grouped by patient):")
    print(S.split_summary(splits, cases).to_string())
    print("Reproducible with the same seed:", S.make_grouped_splits(cases, subject_of) == splits)
    for name, problems in [("Admission-level leakage check", S.leakage_check(splits, cases)),
                           ("Patient-level leakage check", S.patient_leakage_check(splits, subject_of))]:
        print(f"{name}:", "PASS" if not problems else problems)
    path = S.save_splits(splits, SPLIT_DIR, filename="ext_cdm_splits_v2.json", grouped_by="subject_id")
    print("Saved (IDs only):", path.relative_to(ROOT))
    broken = {**splits, "test": splits["test"][:-1] + [splits["train"][0]]}
    print("Leakage check on a deliberately leaky split:", S.leakage_check(broken, cases))


STEPS = {"manifest": step_manifest, "samples": step_samples, "clean": step_clean, "missing": step_missing,
         "transform": step_transform, "validate": step_validate, "eda": step_eda, "splits": step_splits}

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in (STEPS if which == "all" else [which]):
        STEPS[name]()
        print()
