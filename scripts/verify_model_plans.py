"""Verify Model A's plans against rule catalog v2.0, using the real case facts from the record.

Run from the repository root (data in MIMIC_DIR, default ~/data/mimic):
    python scripts/verify_model_plans.py --plans path/to/model_a_plans.json
Plans file: a JSON list of {"case_id", "diagnosis", "treatments", "postop_antibiotic_days"} (docs/model_a_plan_format.md).
For a data-free check use --facts-json (a {"<case_id>": {"pathology": ..., "facts": {...}}} file).
Prints aggregate counts and rule IDs only; per-case results (IDs and rule IDs, no text) go to results/model_runs/.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import load_case_facts  # noqa: E402
from clinverify.eval.model_run import verify_model_plans  # noqa: E402
from clinverify.rules.catalog import catalog  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, type=Path)
    ap.add_argument("--facts-json", type=Path, help="case facts file; skips reading the dataset")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "model_runs")
    args = ap.parse_args()

    outputs = json.loads(args.plans.read_text())
    if args.facts_json:
        case_facts = {int(k): v for k, v in json.loads(args.facts_json.read_text()).items()}
    else:
        case_facts = load_case_facts(o.get("case_id") for o in outputs if isinstance(o, dict) and "case_id" in o)
    summary = verify_model_plans(outputs, case_facts, catalog)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"run_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json"
    path.write_text(json.dumps(summary, indent=1))
    printable = {k: v for k, v in summary.items() if k != "per_case"}
    print(json.dumps(printable, indent=1))
    print("per-case results:", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
