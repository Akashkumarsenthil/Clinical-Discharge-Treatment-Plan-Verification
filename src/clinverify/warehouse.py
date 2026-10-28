"""Local DuckDB warehouse for the Ext-CDM pipeline: raw -> staging -> mart, with a run log and data-quality checks.

The warehouse file holds patient data, so it lives under MIMIC_DIR (outside the repo) and is never committed.

  raw       the downloaded tables as read, one table per file
  staging   cleaned (exact duplicates dropped) and transformed (normalised text, parsed labs) tables
  mart      what the models and the evaluation read: one row per case with its split, the case facts (known facts only;
            a fact the record does not establish has no row), and the per-case model input (text the model may see; no discharge diagnosis, ICD codes or procedures)
  ops       counts only, no patient text: pipeline_runs (one row per run), step_log (one row per step and table),
            dq_results (one row per data-quality check). The monitoring view reads these.

The raw checks gate the load: tables are read and validated in memory first, and a run whose raw checks fail writes
nothing, so the last good warehouse stays as it was. Only the ops tables record the failed run.

Run it from the notebook (`run_pipeline()`) or on a schedule (`python scripts/run_pipeline.py`).
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from clinverify.data import ext_cdm as E
from clinverify.data import splits as S
from clinverify.data.case_loader import case_facts_from_tables
from clinverify.models.model_a import case_inputs

ROOT = Path(__file__).resolve().parents[2]
SPLIT_FILE = ROOT / "data" / "splits" / "ext_cdm_splits_v2.json"
DEFAULT_DB = E.MIMIC_DIR / "warehouse" / "clinverify.duckdb"
EXPECTED_SPLIT_SIZES = {"train": 1840, "val": 460, "test": 100}

OPS_DDL = """
CREATE SCHEMA IF NOT EXISTS raw; CREATE SCHEMA IF NOT EXISTS staging; CREATE SCHEMA IF NOT EXISTS mart; CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.pipeline_runs (run_id VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP, status VARCHAR,
    duration_s DOUBLE, trigger VARCHAR, n_cases INTEGER, n_checks INTEGER, n_checks_failed INTEGER, error VARCHAR);
CREATE TABLE IF NOT EXISTS ops.step_log (run_id VARCHAR, step VARCHAR, table_name VARCHAR, rows_in BIGINT, rows_out BIGINT,
    n_columns INTEGER, seconds DOUBLE);
CREATE TABLE IF NOT EXISTS ops.dq_results (run_id VARCHAR, check_name VARCHAR, layer VARCHAR, status VARCHAR,
    observed VARCHAR, expected VARCHAR);
"""


def connect(db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(OPS_DDL)
    return con


def _write(con, schema: str, name: str, df: pd.DataFrame) -> None:
    con.register("_df", df)
    con.execute(f'CREATE OR REPLACE TABLE {schema}."{name}" AS SELECT * FROM _df')
    con.unregister("_df")


def _count(con, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def _read(directory: Path, mimic_iv_dir: Path, fault: bool):
    tables = E.load_tables(directory)
    tables["lab_test_mapping"] = pd.read_csv(directory / "lab_test_mapping.csv")
    ids = E.load_pathology_ids(directory)
    tables["pathology_ids"] = E.case_table(ids)
    adm_path = mimic_iv_dir / "hosp" / "admissions.csv.gz"
    if adm_path.exists():
        tables["admissions"] = pd.read_csv(adm_path, usecols=["subject_id", "hadm_id"])
    if fault:                                   # demo only: the same breakage the notebook's validation section uses
        tables.update(E.corrupt({k: tables[k] for k in E.CASE_LEVEL + E.EVENT_LEVEL}))
    return tables, ids


def _ingest(con, run_id, log, tables, seconds):
    for name, df in tables.items():
        _write(con, "raw", name, df)
        log.append((run_id, "ingest", name, len(df), len(df), df.shape[1], seconds / len(tables)))


def _stage(con, run_id, log, tables, directory: Path):
    t0 = time.perf_counter()
    case_tables = {k: tables[k] for k in E.CASE_LEVEL + E.EVENT_LEVEL}
    cleaned, _ = E.clean_tables(case_tables)
    transformed = E.transform_tables(cleaned, directory)
    seconds = (time.perf_counter() - t0) / len(transformed)
    for name, df in transformed.items():
        if name == "cases_master":
            continue
        _write(con, "staging", name, df)
        log.append((run_id, "stage", name, len(tables[name]), len(df), df.shape[1], seconds))
    return cleaned, transformed


def _marts(con, run_id, log, tables, transformed, ids, split_file: Path):
    t0 = time.perf_counter()
    splits = json.loads(Path(split_file).read_text())["splits"]
    split_of = {h: name for name, hs in splits.items() for h in hs}
    cases = transformed["cases_master"].copy()
    cases["split"] = cases["hadm_id"].map(split_of)
    if "admissions" in tables:
        cases = cases.merge(tables["admissions"].drop_duplicates("hadm_id"), on="hadm_id", how="left")
    pathology_of = {h: p for p, hs in ids.items() for h in hs}
    facts = case_facts_from_tables(pathology_of, transformed["icd_diagnosis"], transformed["discharge_diagnosis"])
    fact_rows = pd.DataFrame([{"hadm_id": h, "pathology": v["pathology"], "fact": k, "value": val}
                              for h, v in facts.items() for k, val in v["facts"].items()],
                             columns=["hadm_id", "pathology", "fact", "value"])
    inputs = case_inputs(transformed)
    model_inputs = pd.DataFrame({"hadm_id": list(inputs), "model_input": list(inputs.values())})
    model_inputs["input_chars"] = model_inputs["model_input"].str.len()
    model_inputs = model_inputs.merge(cases[["hadm_id", "pathology", "split"]], on="hadm_id", how="left")
    marts = {"cases": cases, "case_facts": fact_rows, "model_inputs": model_inputs}
    seconds = (time.perf_counter() - t0) / len(marts)
    for name, df in marts.items():
        _write(con, "mart", name, df)
        log.append((run_id, "mart", name, None, len(df), df.shape[1], seconds))
    return marts, splits


def _checks(con, tables, ids, splits, have_admissions: bool) -> list[tuple[str, str, str, str]]:
    """(check, layer, observed, expected). A check passes when observed == expected."""
    n_ids = len(E.case_table(ids))
    out = []
    for name in E.CASE_LEVEL:
        out.append((f"staging.{name}: one row per case", "staging",
                    str(_count(con, f'SELECT COUNT(*) - COUNT(DISTINCT hadm_id) FROM staging."{name}"')), "0"))
    out += [
        ("staging.laboratory_tests: no rows lost by transform", "staging",
         str(_count(con, "SELECT COUNT(*) FROM staging.laboratory_tests")),
         str(len(tables["laboratory_tests"].drop_duplicates()))),
        ("staging.laboratory_tests: flag in allowed set", "staging",
         str(_count(con, "SELECT COUNT(*) FROM staging.laboratory_tests WHERE flag NOT IN ('low','normal','high','unknown')")), "0"),
        ("mart.cases: one row per benchmark case", "mart", str(_count(con, "SELECT COUNT(DISTINCT hadm_id) FROM mart.cases")), str(n_ids)),
        ("mart.cases: every case has a split", "mart", str(_count(con, "SELECT COUNT(*) FROM mart.cases WHERE split IS NULL")), "0"),
    ]
    for name, expected in EXPECTED_SPLIT_SIZES.items():
        if len(splits.get(name, [])) == expected:      # only meaningful for the real 2,400-case benchmark
            out.append((f"mart.cases: {name} split size", "mart",
                        str(_count(con, f"SELECT COUNT(*) FROM mart.cases WHERE split = '{name}'")), str(expected)))
    if have_admissions:
        out.append(("mart.cases: no patient in two splits", "mart",
                    str(_count(con, "SELECT COUNT(*) FROM (SELECT subject_id FROM mart.cases WHERE subject_id IS NOT NULL "
                                    "GROUP BY subject_id HAVING COUNT(DISTINCT split) > 1)")), "0"))
    out += [
        ("mart.model_inputs: no empty model input", "mart",
         str(_count(con, "SELECT COUNT(*) FROM mart.model_inputs WHERE input_chars < 50")), "0"),
        ("mart.case_facts: facts only for covered pathologies", "mart",
         str(_count(con, "SELECT COUNT(*) FROM mart.case_facts WHERE pathology NOT IN ('appendicitis','pancreatitis','diverticulitis')")), "0"),
    ]
    return out


def run_pipeline(db_path: Path = DEFAULT_DB, directory: Path = E.EXT_CDM_DIR, mimic_iv_dir: Path = E.MIMIC_IV_DIR,
                 split_file: Path = SPLIT_FILE, trigger: str = "manual", inject_fault: bool = False) -> dict:
    """Run ingest -> stage -> mart -> checks once and log it. Returns the run row plus the check table.
    A failed check marks the run 'failed_checks'. An exception is logged as 'error' (exception type only, so no data value
    can reach the ops tables) and then raised again, so the notebook shows the traceback and a scheduler sees the failure."""
    con = connect(db_path)
    run_id = uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc).replace(tzinfo=None)
    t0 = time.perf_counter()
    log, checks, status, error, n_cases, raised = [], [], "ok", None, None, None
    try:
        t_read = time.perf_counter()
        tables, ids = _read(Path(directory), Path(mimic_iv_dir), inject_fault)
        problems = E.validate_tables({k: tables[k] for k in E.CASE_LEVEL + E.EVENT_LEVEL}, ids)
        checks = [("raw: validate_tables problems (gate)", "raw", str(len(problems)), "0")]
        if not problems:                        # gate: a failed raw check publishes nothing
            _ingest(con, run_id, log, tables, time.perf_counter() - t_read)
            _, transformed = _stage(con, run_id, log, tables, Path(directory))
            marts, splits = _marts(con, run_id, log, tables, transformed, ids, split_file)
            n_cases = len(marts["cases"])
            checks += _checks(con, tables, ids, splits, "admissions" in tables)
    except Exception as err:                    # logged below, then raised again
        status, error, raised = "error", type(err).__name__, err
    dq = pd.DataFrame([(run_id, c, layer, "pass" if obs == exp else "fail", obs, exp) for c, layer, obs, exp in checks],
                      columns=["run_id", "check_name", "layer", "status", "observed", "expected"])
    n_failed = int((dq["status"] == "fail").sum())
    if status == "ok" and n_failed:
        status = "failed_checks"
    duration = time.perf_counter() - t0
    run = {"run_id": run_id, "started_at": started, "finished_at": datetime.now(timezone.utc).replace(tzinfo=None),
           "status": status, "duration_s": round(duration, 2), "trigger": trigger, "n_cases": n_cases,
           "n_checks": len(dq), "n_checks_failed": n_failed, "error": error}
    if log:
        con.executemany("INSERT INTO ops.step_log VALUES (?, ?, ?, ?, ?, ?, ?)", log)
    if len(dq):
        con.executemany("INSERT INTO ops.dq_results VALUES (?, ?, ?, ?, ?, ?)", dq.values.tolist())
    con.execute("INSERT INTO ops.pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(run.values()))
    con.close()
    if raised is not None:
        raise raised
    return {**run, "checks": dq}


def layer_counts(con) -> pd.DataFrame:
    """Tables, rows and columns per warehouse layer (counts only)."""
    tabs = con.execute("SELECT table_schema, table_name FROM information_schema.tables "
                       "WHERE table_schema IN ('raw','staging','mart','ops') ORDER BY 1, 2").fetchall()
    rows = []
    for schema, name in tabs:
        n = _count(con, f'SELECT COUNT(*) FROM {schema}."{name}"')
        cols = _count(con, f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='{schema}' AND table_name='{name}'")
        rows.append({"layer": schema, "table": name, "rows": n, "columns": cols})
    return pd.DataFrame(rows)


def run_history(con, limit: Optional[int] = 20) -> pd.DataFrame:
    sql = "SELECT * FROM ops.pipeline_runs ORDER BY started_at DESC"
    return con.execute(sql + (f" LIMIT {int(limit)}" if limit else "")).df()
