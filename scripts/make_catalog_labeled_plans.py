"""Write tests/data/catalog_labeled_plans.json: synthetic labeled plans for the rule catalog.

Labels come from how each plan was designed (the rule it was built to violate), not from the verifier's output:
each rule's valid example is labeled [], its invalid example [rule id], plus a few plans built to break several rules.
Run from the repository root:  python scripts/make_catalog_labeled_plans.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.rules.catalog import _appendicitis, _diverticulitis, _pancreatitis, catalog  # noqa: E402


def labeled_plans():
    items = []
    for rule in catalog:
        items.append({"plan": rule.valid_example.to_dict(), "violates": []})
        items.append({"plan": rule.invalid_example.to_dict(), "violates": [rule.id]})
    combos = [
        (_appendicitis(9001, treatments=("appendectomy",), days=3), ["R-APP-001", "R-APP-002"]),
        (_appendicitis(9002, complicated=True, days=8), ["R-APP-003"]),
        (_pancreatitis(9003, treatments=("ercp", "antibiotics"), biliary=True, mild=False), ["R-PAN-001", "R-PAN-004"]),
        (_pancreatitis(9004, treatments=("parenteral_nutrition",), necrotizing=True, infection=True, mild=False),
         ["R-PAN-002", "R-PAN-005"]),
        (_diverticulitis(9005, treatments=("antibiotics",), alarm_symptoms=True), ["R-DIV-001", "R-DIV-003"]),
    ]
    items += [{"plan": p.to_dict(), "violates": v} for p, v in combos]
    return items


if __name__ == "__main__":
    out = ROOT / "tests" / "data" / "catalog_labeled_plans.json"
    out.write_text(json.dumps(labeled_plans(), indent=1))
    print(f"wrote {len(labeled_plans())} labeled plans to {out.relative_to(ROOT)}")
