"""Aggregate counts of the derived case facts per pathology: true, false and unknown (no patient text is printed or saved).

Run from the repository root with the data in MIMIC_DIR (default ~/data/mimic):
    python scripts/case_facts_counts.py
Writes docs/case_facts_counts.csv (counts only, safe to commit).
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import load_case_facts  # noqa: E402
from clinverify.rules.catalog import catalog  # noqa: E402


FACTS = {"appendicitis": ["complicated"],
         "pancreatitis": ["necrotizing", "infection", "biliary", "cholangitis", "biliary_obstruction", "mild"],
         "diverticulitis": ["complicated", "alarm_symptoms"]}


def main() -> None:
    splits = json.load(open(ROOT / "data" / "splits" / "ext_cdm_splits_v2.json"))["splits"]
    test_ids = set(splits["test"])
    rows = []
    for mode, sensitivity in (("strict", False), ("sensitivity", True)):
        cases = load_case_facts(sensitivity=sensitivity)       # the same extraction path the verifier uses
        for gname, hadms in (("test (100)", test_ids), ("all cases", set(cases))):
            for path, facts in FACTS.items():
                derived = [c["facts"] for h, c in cases.items() if h in hadms and c["pathology"] == path]
                for fact in facts:
                    true = sum(d.get(fact) is True for d in derived)
                    false = sum(d.get(fact) is False for d in derived)
                    rows.append({"mode": mode, "group": gname, "pathology": path, "cases": len(derived), "fact": fact,
                                 "true": true, "false": false, "unknown": len(derived) - true - false})
    out = pd.DataFrame(rows)
    out_path = ROOT / "docs" / "case_facts_counts.csv"
    out.to_csv(out_path, index=False)
    print(out[out.group == "all cases"].to_string(index=False))
    elig = rule_eligibility(load_case_facts())
    elig.to_csv(ROOT / "docs" / "rule_eligibility_counts.csv", index=False)
    print("\nRule coverage on real cases from the facts alone (strict mode; plan-based conditions not included):")
    print(elig.to_string(index=False))
    print("\nwrote", out_path.relative_to(ROOT))


def rule_eligibility(cases: dict) -> pd.DataFrame:
    """Per rule and diagnosis, from the facts alone (same logic as the verifier, `fact_status`): cases where the rule's fact
    condition holds and every fact it needs is known ("testable_on_facts"), cases where a needed fact is unknown, and cases
    where a known fact contradicts the condition. Conditions that depend on the plan (for example "surgery planned") and
    what a plan could show are not included, so these are the cases where the rule COULD be checked, not cases it was."""
    from clinverify.plan import Plan
    from clinverify.verifier.z3_verifier import fact_status

    rows = []
    for rule in catalog:
        diagnosis = rule.valid_example.diagnosis
        if diagnosis not in FACTS:
            continue
        counts = {"testable": 0, "unknown": 0, "condition_false": 0}
        for h, c in cases.items():
            if c["pathology"] == diagnosis:
                # plan fields come from the model, not the record, so they count as present in this facts-only view
                plan = Plan(case_id=h, diagnosis=diagnosis, facts=c["facts"], postop_antibiotic_days=0)
                counts[fact_status(rule, plan)] += 1
        rows.append({"rule": rule.id, "diagnosis": diagnosis, "advisory": rule.advisory, "testable_on_facts": counts["testable"],
                     "unknown_fact": counts["unknown"], "condition_false": counts["condition_false"]})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
