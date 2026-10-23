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

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data.case_facts import derive_facts  # noqa: E402


FACTS = {"appendicitis": ["complicated"],
         "pancreatitis": ["necrotizing", "infection", "biliary", "cholangitis", "biliary_obstruction", "mild"],
         "diverticulitis": ["complicated", "alarm_symptoms"]}


def main() -> None:
    ids = E.load_pathology_ids()
    pathology_of = {h: p for p, hs in ids.items() for h in hs}
    titles = E.load_tables()["icd_diagnosis"].groupby("hadm_id")["icd_diagnosis"].apply(list).to_dict()
    splits = json.load(open(ROOT / "data" / "splits" / "ext_cdm_splits_v2.json"))["splits"]
    groups = {"test (100)": set(splits["test"]), "all cases": set(pathology_of)}
    rows = []
    for gname, hadms in groups.items():
        for path, facts in FACTS.items():
            cases = [h for h in hadms if pathology_of.get(h) == path]
            derived = [derive_facts(path, titles.get(h, [])) for h in cases]
            for fact in facts:
                true = sum(d.get(fact) is True for d in derived)
                false = sum(d.get(fact) is False for d in derived)
                rows.append({"group": gname, "pathology": path, "cases": len(cases), "fact": fact,
                             "true": true, "false": false, "unknown": len(cases) - true - false})
    out = pd.DataFrame(rows)
    out_path = ROOT / "docs" / "case_facts_counts.csv"
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    print("\nwrote", out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
