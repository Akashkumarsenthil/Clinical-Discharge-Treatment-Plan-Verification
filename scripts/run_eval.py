"""One-command scored run: verify labeled plans against a rule catalog and log the result.

Run from the repository root:
    python scripts/run_eval.py --plans <labeled_plans.json> --rules clinverify.rules.catalog --seed 298

Labeled plans file: a JSON list of {"plan": {...Plan fields...}, "violates": ["R-XXX-001", ...]}.
The run (configuration, seed, git commit, metrics) is written to results/runs/ (gitignored) and printed.
Demo with toy rules and synthetic plans used by the tests:
    python scripts/run_eval.py --plans tests/data/toy_labeled_plans.json --rules tests.toy_rules
"""
import argparse
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from clinverify.eval.harness import evaluate  # noqa: E402
from clinverify.plan import Plan  # noqa: E402


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, type=Path)
    ap.add_argument("--rules", default="clinverify.rules.catalog", help="module that defines `catalog`")
    ap.add_argument("--seed", type=int, default=298)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "runs")
    args = ap.parse_args()

    catalog = importlib.import_module(args.rules).catalog
    if len(catalog) == 0:
        print(f"The rule catalog in {args.rules} is empty. Add team-written rules first (docs/rule_authoring.md).")
        return 2
    labeled = [(Plan.from_dict(item["plan"]), set(item.get("violates", []))) for item in json.loads(args.plans.read_text())]
    metrics = evaluate(labeled, catalog, args.seed)
    run = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_commit": git_commit(),
           "config": {"plans": str(args.plans), "rules": args.rules, "seed": args.seed}, "metrics": metrics}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"run_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_seed{args.seed}.json"
    path.write_text(json.dumps(run, indent=1))
    print(json.dumps(metrics, indent=1))
    print("logged:", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
