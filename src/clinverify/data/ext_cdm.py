"""Load, clean and validate the MIMIC-IV-Ext-CDM tables (Hager et al., 2024 benchmark).

Data is credentialed PhysioNet data: it is read from MIMIC_DIR (outside the repo) and
never written into the repo. Only counts, IDs and aggregate figures leave this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

MIMIC_DIR = Path(os.environ.get("MIMIC_DIR", Path.home() / "data" / "mimic"))
EXT_CDM_DIR = MIMIC_DIR / "mimic-iv-ext-cdm-1.1"
MIMIC_IV_DIR = MIMIC_DIR / "physionet.org" / "files" / "mimiciv" / "3.1"

# one row per case (hadm_id must be unique)
CASE_LEVEL = ["history_of_present_illness", "physical_examination", "discharge_diagnosis"]
# many rows per case
EVENT_LEVEL = ["icd_diagnosis", "icd_procedures", "discharge_procedures",
               "laboratory_tests", "microbiology", "radiology_reports"]
# every case-linked table, with the columns we rely on
REQUIRED_COLUMNS = {
    "history_of_present_illness": {"hadm_id"},
    "physical_examination": {"hadm_id"},
    "discharge_diagnosis": {"hadm_id"},
    "icd_diagnosis": {"hadm_id"},
    "icd_procedures": {"hadm_id"},
    "discharge_procedures": {"hadm_id"},
    "laboratory_tests": {"hadm_id"},
    "microbiology": {"hadm_id"},
    "radiology_reports": {"hadm_id"},
}
# tables where every case should appear at least once
FULL_COVERAGE = ["history_of_present_illness", "physical_examination", "discharge_diagnosis",
                 "icd_diagnosis", "laboratory_tests", "radiology_reports"]


def load_pathology_ids(directory: Path = EXT_CDM_DIR) -> dict[str, list[int]]:
    with open(directory / "pathology_ids.json") as fh:
        return json.load(fh)


def case_table(ids: dict[str, list[int]]) -> pd.DataFrame:
    """hadm_id -> pathology label (the stratification label)."""
    rows = [(int(h), p) for p, hs in ids.items() for h in hs]
    return pd.DataFrame(rows, columns=["hadm_id", "pathology"])


def load_tables(directory: Path = EXT_CDM_DIR) -> dict[str, pd.DataFrame]:
    return {name: pd.read_csv(directory / f"{name}.csv")
            for name in CASE_LEVEL + EVENT_LEVEL}


def clean_tables(tables: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Drop exact duplicate rows and report before/after counts and missingness."""
    cleaned, report = {}, []
    for name, df in tables.items():
        dedup = df.drop_duplicates().reset_index(drop=True)
        report.append({
            "table": name,
            "rows_before": len(df),
            "duplicate_rows": len(df) - len(dedup),
            "rows_after": len(dedup),
            "null_cells_pct": round(float(dedup.isna().mean().mean() * 100), 2),
            "cases_covered": int(dedup["hadm_id"].nunique()) if "hadm_id" in dedup else None,
        })
        cleaned[name] = dedup
    return cleaned, pd.DataFrame(report)


def validate_tables(tables: dict[str, pd.DataFrame], ids: dict[str, list[int]]) -> list[str]:
    """Return a list of human-readable problems; an empty list means all checks pass."""
    problems: list[str] = []
    cases = case_table(ids)
    expected = set(cases["hadm_id"])
    if len(expected) != len(cases):
        problems.append(f"pathology_ids: {len(cases) - len(expected)} hadm_id appear under more than one pathology")
    for name, cols in REQUIRED_COLUMNS.items():
        if name not in tables:
            problems.append(f"{name}: table missing")
            continue
        missing = cols - set(tables[name].columns)
        if missing:
            problems.append(f"{name}: missing columns {sorted(missing)}")
    for name in CASE_LEVEL:
        df = tables.get(name)
        if df is not None and "hadm_id" in df and df["hadm_id"].duplicated().any():
            problems.append(f"{name}: {int(df['hadm_id'].duplicated().sum())} duplicated hadm_id in a one-row-per-case table")
    for name, df in tables.items():
        if "hadm_id" not in df:
            continue
        unknown = set(df["hadm_id"].dropna()) - expected
        if unknown:
            problems.append(f"{name}: {len(unknown)} hadm_id not in pathology_ids.json")
        if df["hadm_id"].isna().any():
            problems.append(f"{name}: {int(df['hadm_id'].isna().sum())} rows with empty hadm_id")
    for name in FULL_COVERAGE:
        df = tables.get(name)
        if df is not None and "hadm_id" in df:
            absent = expected - set(df["hadm_id"].dropna())
            if absent:
                problems.append(f"{name}: {len(absent)} cases have no rows")
    hpi = tables.get("history_of_present_illness")
    if hpi is not None:
        text_cols = [c for c in hpi.columns if c != "hadm_id"]
        for c in text_cols:
            empty = int(hpi[c].isna().sum() + (hpi[c].astype(str).str.strip() == "").sum())
            if empty:
                problems.append(f"history_of_present_illness.{c}: {empty} empty values")
    return problems


def corrupt(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Deliberately break a copy of the tables (used to show the checks really fail)."""
    bad = {k: v.copy() for k, v in tables.items()}
    hpi = bad["history_of_present_illness"]
    bad["history_of_present_illness"] = pd.concat([hpi, hpi.iloc[:3]], ignore_index=True)      # duplicate cases
    text_col = [c for c in hpi.columns if c != "hadm_id"][0]
    bad["history_of_present_illness"].loc[:9, text_col] = None                                  # empty text
    bad["laboratory_tests"] = bad["laboratory_tests"].drop(columns=["hadm_id"])                 # schema break
    bad["microbiology"].loc[:4, "hadm_id"] = -1                                                 # unknown case id
    bad["radiology_reports"] = bad["radiology_reports"][bad["radiology_reports"]["hadm_id"] > bad["radiology_reports"]["hadm_id"].quantile(0.01)]  # lost cases
    return bad


# ---------------------------------------------------------------- transformations
TEXT_COLUMNS = {"history_of_present_illness": "hpi", "physical_examination": "pe",
                "radiology_reports": "text", "discharge_diagnosis": "discharge_diagnosis"}

TRANSFORM_LOG = [
    # (table, input, operation, output, rationale)
    ("text tables (hpi, pe, radiology, discharge dx)", "raw free text", "strip, collapse repeated whitespace, cast to str",
     "normalised text + word_count", "consistent formatting; length is a simple input-size feature"),
    ("laboratory_tests", "valuestr (e.g. '2.5 mmol/L')", "split into number, unit and '<'/'>' qualifier; non-numeric results (e.g. NEG) stay as text",
     "value (float), unit, qualifier, value_is_numeric", "numeric comparison against reference range"),
    ("laboratory_tests", "value, ref_range_lower/upper", "flag low / normal / high; 'unknown' if range missing",
     "flag", "abnormal-only views of labs; no invented reference ranges"),
    ("lab_test_mapping", "itemid (float, some null)", "drop rows without itemid, cast to int",
     "itemid (int), label", "join readable lab names onto laboratory_tests"),
    ("all case tables", "hadm_id + pathology_ids.json", "join pathology label to each case",
     "cases_master (hadm_id, pathology, counts per table)", "label for stratified splits and per-class EDA"),
]

MISSING_RULES = {
    ("laboratory_tests", "ref_range_lower"): "keep as missing; flag = 'unknown' (not imputed: reference ranges are lab-specific facts)",
    ("laboratory_tests", "ref_range_upper"): "keep as missing; flag = 'unknown' (same reason)",
    ("lab_test_mapping", "itemid"): "drop row (cannot be joined)",
    ("lab_test_mapping", "fluid"): "keep as missing (descriptive only)",
    ("lab_test_mapping", "category"): "keep as missing (descriptive only)",
    ("lab_test_mapping", "count"): "keep as missing (descriptive only)",
    ("discharge_procedures", "discharge_procedure"): "drop row (empty procedure)",
}


def missing_report(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in tables.items():
        for col, n in df.isna().sum().items():
            if n:
                rows.append({"table": name, "column": col, "missing": int(n),
                             "missing_pct": round(n / len(df) * 100, 1),
                             "handling": MISSING_RULES.get((name, col), "review")})
    return pd.DataFrame(rows)


def _norm_text(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def transform_tables(cleaned: dict[str, pd.DataFrame], directory: Path = EXT_CDM_DIR) -> dict[str, pd.DataFrame]:
    out = {k: v.copy() for k, v in cleaned.items()}
    for name, col in TEXT_COLUMNS.items():
        out[name][col] = _norm_text(out[name][col])
        out[name]["word_count"] = out[name][col].str.split().str.len()
    out["discharge_procedures"] = out["discharge_procedures"].dropna(subset=["discharge_procedure"]).reset_index(drop=True)
    mapping = pd.read_csv(directory / "lab_test_mapping.csv").dropna(subset=["itemid"])
    mapping["itemid"] = mapping["itemid"].astype(int)
    mapping = mapping.drop_duplicates("itemid")
    labs = out["laboratory_tests"]
    parts = labs["valuestr"].astype(str).str.extract(r"^\s*(?P<qual>[<>]=?)?\s*(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>.*)$")
    labs["value"] = pd.to_numeric(parts["num"], errors="coerce")
    labs["unit"] = parts["unit"].where(parts["num"].notna()).str.strip().replace("", pd.NA)
    labs["qualifier"] = parts["qual"]            # '<' or '>' means the true value is beyond the printed number
    labs["value_is_numeric"] = labs["value"].notna()
    flag = pd.Series("unknown", index=labs.index)
    has_range = labs["ref_range_lower"].notna() & labs["ref_range_upper"].notna() & labs["value"].notna()
    flag[has_range & (labs["value"] < labs["ref_range_lower"])] = "low"
    flag[has_range & (labs["value"] > labs["ref_range_upper"])] = "high"
    flag[has_range & labs["value"].between(labs["ref_range_lower"], labs["ref_range_upper"])] = "normal"
    labs["flag"] = flag
    out["laboratory_tests"] = labs.merge(mapping[["itemid", "label"]], on="itemid", how="left")
    ids = load_pathology_ids(directory)
    master = case_table(ids)
    for name in ("laboratory_tests", "microbiology", "radiology_reports", "icd_diagnosis"):
        master = master.merge(out[name].groupby("hadm_id").size().rename(f"n_{name}"), on="hadm_id", how="left")
    master["hpi_words"] = master["hadm_id"].map(out["history_of_present_illness"].set_index("hadm_id")["word_count"])
    out["cases_master"] = master.fillna(0)
    return out
