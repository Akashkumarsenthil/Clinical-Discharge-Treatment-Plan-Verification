"""Show one admission record at a time for the blind eligibility review, and write the reviewer's answers to a working sheet.

Run from the repository root on a machine that holds your own approved copy of MIMIC-IV-Ext-CDM (MIMIC_DIR, default ~/data/mimic):
    MIMIC_DIR=~/data/mimic python scripts/eligibility_record_view.py --work ~/eligibility_work.csv

For each of the 73 case IDs in docs/eligibility_review_sheet.csv it prints the reference diagnosis and the record as it stood
before treatment decisions: history, physical examination, laboratory results, microbiology and imaging reports, in full
(not shortened as in Model A's input). It does NOT print the discharge diagnosis, ICD codes or procedures, and it never reads
case facts, rule coverage, generated plans, model outputs or verifier verdicts. Answer y or n; for n give a short reason in your
own words, without patient text. Answers are saved after every case, so you can stop and resume. Keep the working file OUTSIDE
the repository until the manifest is built (docs/eligibility_review_guide.md).
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "docs" / "eligibility_review_sheet.csv"
FIELDS = ["case_id", "eligible_yes_no", "reason_if_no"]


def ext_cdm_dir() -> Path:
    return Path(os.environ.get("MIMIC_DIR", "~/data/mimic")).expanduser() / "mimic-iv-ext-cdm-1.1"


def reference_diagnosis(directory: Path) -> dict[int, str]:
    with open(directory / "pathology_ids.json") as fh:
        return {int(h): p for p, hs in json.load(fh).items() for h in hs}


def record_text(directory: Path, tables: dict[str, pd.DataFrame], h: int) -> str:
    def one(name: str, col: str) -> str:
        df = tables[name]
        hit = df.loc[df["hadm_id"] == h, col]
        return str(hit.iloc[0]) if len(hit) else "(none in the record)"

    parts = [f"HISTORY OF PRESENT ILLNESS\n{one('history_of_present_illness', 'hpi')}",
             f"PHYSICAL EXAMINATION\n{one('physical_examination', 'pe')}"]
    labs = tables["laboratory_tests"]
    labs = labs[labs["hadm_id"] == h]
    names = tables["lab_test_mapping"].drop_duplicates("itemid").set_index("itemid")["label"]
    lines = []
    for _, r in labs.iterrows():
        label = names.get(r["itemid"], f"item {r['itemid']}")
        low, high = r.get("ref_range_lower"), r.get("ref_range_upper")
        rng = f" (ref {low} to {high})" if pd.notna(low) and pd.notna(high) else ""
        lines.append(f"- {label}: {r['valuestr']}{rng}")
    parts.append("LABORATORY RESULTS\n" + ("\n".join(lines) if lines else "(none in the record)"))
    micro = tables["microbiology"]
    micro = micro[micro["hadm_id"] == h]
    parts.append("MICROBIOLOGY\n" + ("\n".join(f"- {v}" for v in micro["valuestr"].astype(str)) if len(micro) else "(none in the record)"))
    rad = tables["radiology_reports"]
    rad = rad[rad["hadm_id"] == h]
    parts.append("IMAGING\n" + ("\n\n".join(f"{r['modality']} {r['region']} ({r['exam_name']}):\n{r['text']}" for _, r in rad.iterrows())
                                if len(rad) else "(none in the record)"))
    return "\n\n".join(parts)


def load_answers(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {int(r["case_id"]): r for r in csv.DictReader(f)}


def save_answers(path: Path, ids: list[int], answers: dict[int, dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for h in ids:
            w.writerow(answers.get(h, {"case_id": h, "eligible_yes_no": "", "reason_if_no": ""}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True, type=Path, help="working sheet to write (keep it outside the repository)")
    ap.add_argument("--sheet", type=Path, default=SHEET, help="blank sheet listing the case IDs")
    ap.add_argument("--data-dir", type=Path, default=None, help="Ext-CDM folder (default MIMIC_DIR/mimic-iv-ext-cdm-1.1)")
    args = ap.parse_args()
    work = args.work.expanduser()
    if ROOT in work.resolve().parents:
        ap.error("keep the working sheet outside the repository until the manifest is built")
    directory = args.data_dir or ext_cdm_dir()
    with args.sheet.open(newline="") as f:
        ids = [int(r["case_id"]) for r in csv.DictReader(f)]
    names = ["history_of_present_illness", "physical_examination", "laboratory_tests", "microbiology", "radiology_reports"]
    tables = {n: pd.read_csv(directory / f"{n}.csv") for n in names}
    tables["lab_test_mapping"] = pd.read_csv(directory / "lab_test_mapping.csv")
    diagnosis = reference_diagnosis(directory)
    answers = load_answers(work)
    for i, h in enumerate(ids, 1):
        if answers.get(h, {}).get("eligible_yes_no") in ("yes", "no"):
            continue
        print("\n" + "=" * 100)
        print(f"Case {i} of {len(ids)}   id {h}   reference diagnosis: {diagnosis.get(h, 'unknown')}")
        print("=" * 100)
        print(record_text(directory, tables, h))
        print("\nDoes this record contain enough information for a clinician to judge whether a treatment plan for the reference "
              "diagnosis is clinically adequate and valid?")
        while True:
            choice = input("[y] yes   [n] no   [q] save and quit > ").strip().lower()
            if choice in ("y", "n", "q"):
                break
        if choice == "q":
            break
        reason = ""
        if choice == "n":
            while not reason:
                reason = input("Reason (your own words, no patient text) > ").strip()
        answers[h] = {"case_id": h, "eligible_yes_no": "yes" if choice == "y" else "no", "reason_if_no": reason}
        save_answers(work, ids, answers)
    save_answers(work, ids, answers)
    done = sum(answers.get(h, {}).get("eligible_yes_no") in ("yes", "no") for h in ids)
    print(f"\n{done} of {len(ids)} cases answered. Working sheet: {work}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
