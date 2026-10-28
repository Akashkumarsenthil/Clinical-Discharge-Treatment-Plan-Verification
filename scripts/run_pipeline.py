"""Run the warehouse pipeline once (raw -> staging -> mart -> data-quality checks) and log the run.

Run from the repository root (data in MIMIC_DIR, default ~/data/mimic):
    python scripts/run_pipeline.py                      # build or refresh the warehouse
    python scripts/run_pipeline.py --history            # show the last runs (counts only)
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=W.DEFAULT_DB, help="DuckDB file (default MIMIC_DIR/warehouse/clinverify.duckdb)")
    ap.add_argument("--split-file", type=Path, default=W.SPLIT_FILE)
    ap.add_argument("--trigger", default="manual", help="recorded in ops.pipeline_runs (manual, cron, notebook)")
    ap.add_argument("--history", action="store_true", help="print the last 20 runs and exit")
    args = ap.parse_args()
    if args.history:
        con = W.connect(args.db)
        print(W.run_history(con).to_string(index=False))
        return 0
    try:
        run = W.run_pipeline(args.db, split_file=args.split_file, trigger=args.trigger)
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
