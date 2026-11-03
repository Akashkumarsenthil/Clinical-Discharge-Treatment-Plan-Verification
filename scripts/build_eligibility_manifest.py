"""Build and check the eligibility manifest from the filled review sheet (docs/eligibility_review_sheet.csv).

Run from the repository root after the reviewer has filled every row:
    python scripts/build_eligibility_manifest.py --sheet filled_sheet.csv --reviewer AS --date 2026-11-10 --blind-to-plans
Pass --blind-to-plans only if the reviewer judged the records without seeing any generated plan, model name or verifier verdict.
Writes the manifest (case IDs, yes/no, short reasons; no patient text) and prints its SHA-256 for the freeze record.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import load_case_facts  # noqa: E402
from clinverify.eval.adjudication import manifest_from_review_rows, validate_eligibility_manifest  # noqa: E402
from clinverify.eval.protocol import cohort_ids, load_protocol, treatment_cohort_record  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, type=Path)
    ap.add_argument("--reviewer", required=True, help="initials")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--blind-to-plans", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "eligibility_manifest.json")
    args = ap.parse_args()
    protocol = load_protocol()
    ids = cohort_ids("test")
    facts = load_case_facts(ids)
    treatment_cohort_record(ids, facts, protocol, formal_test=True)         # raises if the covered 73 differ from the frozen set
    covered = {h for h in ids if facts[h]["pathology"] in protocol["treatment_diagnoses"]}
    with args.sheet.open(newline="") as f:
        rows = list(csv.DictReader(f))
    try:
        manifest = manifest_from_review_rows(rows, reviewer=args.reviewer, review_date=args.date,
                                             blind_to_plans=args.blind_to_plans, catalog_version=protocol["catalog_version"])
        result = validate_eligibility_manifest(manifest, covered_case_ids=covered, catalog_version=protocol["catalog_version"])
    except ValueError as err:
        ap.error(str(err))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=1))
    print(f"covered {result['n_covered']}, eligible {result['n_eligible']}, ineligible {result['n_ineligible']}")
    print("reasons:", result["ineligibility_reasons"])
    print("manifest sha256:", result["manifest_sha256"])
    print("written:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
