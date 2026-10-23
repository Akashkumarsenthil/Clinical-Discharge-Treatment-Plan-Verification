"""Draw a stratified sample of cases for a manual audit of the derived case facts.

LOCAL USE ONLY. The output holds each case's diagnosis titles and discharge text (patient data): it is written to
results/audit_sample.csv, which Git ignores. Do not commit it, paste it into a chat tool, or send it to a hosted model.

For every (pathology, fact, derived value) it takes up to N random cases (seed 298), including the "unknown" strata
(to find evidence the extraction missed), and flags the cases whose value came only from the discharge text, because
those are the newly upgraded ones. For an unknown row the reviewer answers "yes" if the unknown is right (the record
really does not establish the fact) and "no" if the record does establish it. A reviewer fills the last column.
    python scripts/sample_for_audit.py --per-stratum 5
"""
import argparse
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data.case_facts import derive_facts  # noqa: E402
from clinverify.data.case_loader import load_case_facts  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-stratum", type=int, default=5)
    args = ap.parse_args()
    cases = load_case_facts()
    tables = E.load_tables()
    titles = tables["icd_diagnosis"].groupby("hadm_id")["icd_diagnosis"].apply(list).to_dict()
    discharge = tables["discharge_diagnosis"].groupby("hadm_id")["discharge_diagnosis"].apply(lambda s: " ".join(map(str, s))).to_dict()
    strata: dict[tuple, list] = {}
    for h, c in cases.items():
        text_only = derive_facts(c["pathology"], titles.get(h, []), "")          # what the codes alone give
        for fact, value in c["facts"].items():
            source = "discharge text" if text_only.get(fact) is None else "icd titles"
            strata.setdefault((c["pathology"], fact, value, source), []).append(h)
    # unknown strata: facts the extraction left out, to look for evidence it missed
    wanted = {"appendicitis": ["complicated"], "diverticulitis": ["complicated", "alarm_symptoms"],
              "pancreatitis": ["necrotizing", "infection", "biliary", "cholangitis", "biliary_obstruction", "mild"]}
    for h, c in cases.items():
        for fact in wanted.get(c["pathology"], []):
            if c["facts"].get(fact) is None:
                strata.setdefault((c["pathology"], fact, "unknown", "none"), []).append(h)
    rng = random.Random(298)
    rows = []
    for (path, fact, value, source), hadms in sorted(strata.items(), key=lambda kv: tuple(map(str, kv[0]))):
        for h in rng.sample(hadms, min(args.per_stratum, len(hadms))):
            rows.append({"hadm_id": h, "pathology": path, "fact": fact, "derived_value": value, "evidence_source": source,
                         "icd_titles": " | ".join(titles.get(h, [])), "discharge_diagnosis": discharge.get(h, ""),
                         "reviewer_agrees (yes/no/unsure)": "", "reviewer_note": ""})
    out = ROOT / "results" / "audit_sample.csv"
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(len(rows), "rows in", len(strata), "strata ->", out.relative_to(ROOT), "(local only, never commit)")


if __name__ == "__main__":
    main()
