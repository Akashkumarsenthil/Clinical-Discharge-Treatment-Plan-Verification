"""Run the warehouse pipeline once (raw -> staging -> mart -> data-quality checks) and log the run.

Run from the repository root (data in MIMIC_DIR, default ~/data/mimic):
    python scripts/run_pipeline.py                      # build or refresh the warehouse
    python scripts/run_pipeline.py --history            # show the last runs (counts only)
    python scripts/run_pipeline.py --tables             # tables, rows and columns per layer (counts only)
    python scripts/run_pipeline.py --inject-fault --trigger demo-fault   # gate demo: rejected, nothing published
On synthetic data (MIMIC_DIR made by make_synthetic_data.py) the split file defaults to the one data_demo.py wrote
under results/synthetic/splits/, so run `data_demo.py all` (or `data_demo.py splits`) first.
Schedule it with cron, for example every night at 02:00:
    0 2 * * * cd /path/to/repo && MIMIC_DIR=$HOME/data/mimic .venv/bin/python scripts/run_pipeline.py --trigger cron >> $HOME/data/mimic/warehouse/cron.log 2>&1
Exit code: 0 ok, 1 a data-quality check failed, 2 the run raised an error (a scheduler or monitor can alert on non-zero).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify import warehouse as W  # noqa: E402
from clinverify.data import ext_cdm as E  # noqa: E402

# Same rule as data_demo.py: synthetic data uses the synthetic split file, never the real committed one.
SYNTHETIC = (E.MIMIC_DIR / "SYNTHETIC").exists()
DEFAULT_SPLIT_FILE = ROOT / "results" / "synthetic" / "splits" / "ext_cdm_splits_v2.json" if SYNTHETIC else W.SPLIT_FILE


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=W.DEFAULT_DB, help="DuckDB file (default MIMIC_DIR/warehouse/clinverify.duckdb)")
    ap.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    ap.add_argument("--trigger", default="manual", help="recorded in ops.pipeline_runs (manual, cron, notebook)")
    ap.add_argument("--history", action="store_true", help="print the last 20 runs and exit")
    ap.add_argument("--tables", action="store_true", help="print tables, rows and columns per warehouse layer and exit")
    ap.add_argument("--inject-fault", action="store_true",
                    help="demo: load a corrupted copy; the gate must reject it and publish nothing (exit 1)")
    args = ap.parse_args()
    if args.history:
        con = W.connect(args.db)
        print(W.run_history(con).to_string(index=False))
        return 0
    if args.tables:
        con = W.connect(args.db)
        print(W.layer_counts(con).to_string(index=False))
        return 0
    if SYNTHETIC and not args.split_file.exists():
        print(f"split file not found: {args.split_file} (on synthetic data run `data_demo.py splits` first)", file=sys.stderr)
        return 2
    try:
        run = W.run_pipeline(args.db, split_file=args.split_file, trigger=args.trigger, inject_fault=args.inject_fault)
    except Exception as err:                    # already logged in ops.pipeline_runs as status 'error'
        print(f"pipeline error: {type(err).__name__}", file=sys.stderr)
        return 2
    checks = run.pop("checks")
    print(json.dumps(run, default=str, indent=1))
    failed = checks[checks["status"] == "fail"]
    if len(failed):
        print(failed.to_string(index=False))
    return 0 if run["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
