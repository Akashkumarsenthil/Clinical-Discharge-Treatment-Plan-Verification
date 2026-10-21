"""Patient-level leakage check for the fixed splits.

The splits are lists of admission IDs (hadm_id). One patient (subject_id) can have several
admissions, so the same patient could appear in two splits. This script maps every split
admission to its patient through MIMIC-IV `admissions` and reports patients that cross splits.

Run from the repository root:   python scripts/patient_overlap_check.py
Checks every data/splits/ext_cdm_splits_v*.json file. Reads patient IDs from $MIMIC_DIR (default ~/data/mimic); prints counts only, never IDs of patients.
"""
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MIMIC_DIR = Path(os.environ.get("MIMIC_DIR", Path.home() / "data" / "mimic"))
ADMISSIONS = MIMIC_DIR / "physionet.org" / "files" / "mimiciv" / "3.1" / "hosp" / "admissions.csv.gz"
SPLITS_DIR = ROOT / ("results" / Path("synthetic") / "splits" if (MIMIC_DIR / "SYNTHETIC").exists() else Path("data") / "splits")

patient_of = pd.read_csv(ADMISSIONS, usecols=["subject_id", "hadm_id"]).set_index("hadm_id")["subject_id"]
for path in sorted(SPLITS_DIR.glob("ext_cdm_splits_v*.json")):
    splits = json.loads(path.read_text())["splits"]
    cases = [h for ids in splits.values() for h in ids]
    patients = patient_of.loc[cases]
    print(f"{path.name}: cases {len(cases)} | distinct patients {patients.nunique()} | "
          f"cases sharing a patient with another case {int(patients.duplicated(keep=False).sum())}")
    by_split = {name: set(patient_of.loc[ids]) for name, ids in splits.items()}
    total = 0
    for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
        n = len(by_split[a] & by_split[b])
        total += n
        print(f"  patients in both {a} and {b}: {n}")
    print("  RESULT:", "PASS (no patient in two splits)" if total == 0 else f"FAIL ({total} patients cross splits)")
