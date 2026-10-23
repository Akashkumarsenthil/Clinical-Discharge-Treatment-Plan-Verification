"""Aggregate counts of the derived case facts per pathology (no patient text is printed or saved).

Run from the repository root with the data in MIMIC_DIR (default ~/data/mimic):
    python scripts/case_facts_counts.py
Writes docs/case_facts_counts.csv (counts only, safe to commit).
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data.case_facts import derive_facts  # noqa: E402


def main() -> None:
    ids = E.load_pathology_ids()
    pathology_of = {h: p for p, hs in ids.items() for h in hs}
    tables = E.load_tables()
    icd = tables["icd_diagnosis"]
    titles = icd.groupby("hadm_id")["icd_diagnosis"].apply(list).to_dict()
    splits = json.load(open(ROOT / "data" / "splits" / "ext_cdm_splits_v2.json"))["splits"]
    groups = {"test (100)": set(splits["test"]), "all cases": set(pathology_of)}
    rows = []
    for gname, hadms in groups.items():
        count = defaultdict(Counter)       # (pathology, fact) -> Counter(True/False/not derived)
        n = Counter()
        for h in hadms:
            path = pathology_of.get(h)
            if path is None:
                continue
            n[path] += 1
            facts = derive_facts(path, titles.get(h, []))
            if not facts:
                count[(path, "(no matching diagnosis title)")]["n"] += 1
                continue
            for fact, val in facts.items():
                count[(path, fact)][str(val)] += 1
        for (path, fact), c in sorted(count.items()):
            rows.append({"group": gname, "pathology": path, "cases": n[path], "fact": fact,
                         "true": c.get("True", 0), "false": c.get("False", 0), "no_title_match": c.get("n", 0)})
    out = pd.DataFrame(rows)
    out_path = ROOT / "docs" / "case_facts_counts.csv"
    out.to_csv(out_path, index=False)
    print(out.to_string(index=False))
    print("\nwrote", out_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
