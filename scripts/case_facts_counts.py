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
    print("\nRule eligibility on real cases (strict mode; plan-based conditions such as 'surgery planned' not included):")
    print(elig.to_string(index=False))
    print("\nwrote", out_path.relative_to(ROOT))


def rule_eligibility(cases: dict) -> pd.DataFrame:
    """Per rule and diagnosis: cases where the rule's fact condition holds and all facts it needs are known (testable),
    cases where a needed fact is unknown (cannot be decided) and cases where a known fact contradicts the condition."""
    rows = []
    for rule in catalog:
        diagnosis = rule.valid_example.diagnosis
        if diagnosis not in FACTS:
            continue
        facts_needed = [r[6:] for r in rule.requires if r.startswith("facts.")]
        for gname, in_group in (("all cases", lambda h: True),):
            testable = unknown = not_applicable = 0
            for h, c in cases.items():
                if c["pathology"] != diagnosis or not in_group(h):
                    continue
                f = c["facts"]
                if any(f.get(k) is not None and bool(f[k]) != v for k, v in rule.condition_facts):
                    not_applicable += 1
                elif any(f.get(k) is None for k in facts_needed):
                    unknown += 1
                else:
                    testable += 1
            rows.append({"rule": rule.id, "diagnosis": diagnosis, "advisory": rule.advisory, "testable": testable,
                         "unknown_fact": unknown, "condition_false": not_applicable})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
