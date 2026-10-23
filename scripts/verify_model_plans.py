"""Verify Model A's plans against rule catalog v2.1, using the real case facts from the record.

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
from clinverify.rules.catalog import CATALOG_VERSION, catalog  # noqa: E402
from clinverify.eval.protocol import cohort_ids, load_protocol, run_provenance, treatment_cohort_record, validate_generation_metadata  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, type=Path)
    ap.add_argument("--facts-json", type=Path, help="case facts file; skips reading the dataset")
    ap.add_argument("--cohort", choices=("pilot", "validation", "test"), default="pilot",
                    help="pilot scores submitted outputs only; validation/test enforce the fixed split and count missing outputs")
    ap.add_argument("--generation-metadata", type=Path,
                    help="JSON with exact model/digest, prompt hash, seed and decoding settings; required for test")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "model_runs")
    args = ap.parse_args()

    outputs = json.loads(args.plans.read_text())
    if not isinstance(outputs, list):
        ap.error("plans file must contain a JSON list")
    expected = cohort_ids(args.cohort)
    protocol = load_protocol()
    if args.cohort != "pilot" and CATALOG_VERSION != protocol["catalog_version"]:
        ap.error("catalog version differs from the frozen evaluation protocol")
    metadata = json.loads(args.generation_metadata.read_text()) if args.generation_metadata else None
    if args.cohort == "test":
        try:
            validate_generation_metadata(metadata, protocol)
        except ValueError as err:
            ap.error(str(err))
    if args.facts_json:
        case_facts = {int(k): v for k, v in json.loads(args.facts_json.read_text()).items()}
    else:
        wanted = expected if expected is not None else [o.get("case_id") for o in outputs if isinstance(o, dict) and type(o.get("case_id")) is int]
        case_facts = load_case_facts(wanted)
    try:
        cohort_record = treatment_cohort_record(expected, case_facts, protocol, formal_test=args.cohort == "test") if expected is not None else None
        summary = verify_model_plans(outputs, case_facts, catalog, expected_case_ids=expected,
                                     supported_diagnoses=protocol["treatment_diagnoses"])
    except ValueError as err:
        ap.error(str(err))
    summary["evaluation"] = {"cohort": args.cohort, "cohort_record": cohort_record, "generation": metadata,
                             "facts_source": "provided_json" if args.facts_json else "local_ext_cdm", **run_provenance()}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"run_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}.json"
    path.write_text(json.dumps(summary, indent=1))
    # Raw parser errors may quote model text. Keep them local, not in aggregate console output.
    printable = {k: v for k, v in summary.items() if k not in ("per_case", "unparseable")}
    print(json.dumps(printable, indent=1))
    print("per-case results:", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
