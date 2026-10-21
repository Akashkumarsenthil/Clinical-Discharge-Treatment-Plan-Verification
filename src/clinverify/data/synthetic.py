"""Generate a SYNTHETIC dataset with the same layout and schema as MIMIC-IV-Ext-CDM (plus MIMIC-IV admissions).

Purpose: lets anyone (TA, other teams, CI) run the whole data pipeline from a clean clone without credentialed
PhysioNet access. Every value is random or boilerplate text; nothing is derived from real patients.

    python scripts/make_synthetic_data.py --out ~/synthetic_mimic
    MIMIC_DIR=~/synthetic_mimic python scripts/data_demo.py all
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

PATHOLOGY_SHARE = {"appendicitis": 0.40, "cholecystitis": 0.27, "pancreatitis": 0.22, "diverticulitis": 0.11}
LABS = [(50931, "Glucose", "mg/dL", 70, 100), (51222, "Hemoglobin", "g/dL", 12, 16), (50912, "Creatinine", "mg/dL", 0.5, 1.2),
        (51221, "Hematocrit", "%", 36, 48), (51301, "White Blood Cells", "K/uL", 4, 11), (51006, "Urea Nitrogen", "mg/dL", 6, 20),
        (50813, "Lactate", "mmol/L", 0.5, 2.0), (50868, "Anion Gap", "mEq/L", 8, 16)]
MODALITIES = ["Radiograph", "CT", "Ultrasound", "MRCP"]
FIRST_ID = 20_000_000


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def generate(out_dir: Path, n_cases: int = 600, seed: int = 298) -> Path:
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    ext = out_dir / "mimic-iv-ext-cdm-1.1"
    hosp = out_dir / "physionet.org" / "files" / "mimiciv" / "3.1" / "hosp"
    ext.mkdir(parents=True, exist_ok=True); hosp.mkdir(parents=True, exist_ok=True)

    hadm = np.arange(FIRST_ID, FIRST_ID + n_cases)
    counts = {k: int(round(v * n_cases)) for k, v in PATHOLOGY_SHARE.items()}
    counts["appendicitis"] += n_cases - sum(counts.values())
    labels = np.concatenate([[k] * v for k, v in counts.items()])
    rng.shuffle(labels)
    ids = {k: [int(h) for h, l in zip(hadm, labels) if l == k] for k in PATHOLOGY_SHARE}
    (ext / "pathology_ids.json").write_text(json.dumps(ids))

    subject = {int(h): 1_000_000 + i for i, h in enumerate(hadm)}          # one patient per admission ...
    for i in rng.choice(n_cases - 1, size=max(1, n_cases // 40), replace=False):
        if labels[i] == labels[i + 1]:
            subject[int(hadm[i + 1])] = subject[int(hadm[i])]               # ... except a few repeat patients

    def per_case(text):
        return pd.DataFrame({"hadm_id": hadm, **text})

    per_case({"hpi": [f"SYNTHETIC history note for case {h}. " + "Pain reported. " * int(rng.integers(3, 60)) for h in hadm]}
             ).to_csv(ext / "history_of_present_illness.csv", index=False)
    per_case({"pe": [f"SYNTHETIC exam for case {h}: vitals recorded." for h in hadm]}).to_csv(ext / "physical_examination.csv", index=False)
    per_case({"discharge_diagnosis": [f"SYNTHETIC diagnosis: {l}" for l in labels]}).to_csv(ext / "discharge_diagnosis.csv", index=False)

    icd = pd.DataFrame([(h, f"SYN{int(rng.integers(100, 999))}") for h in hadm for _ in range(int(rng.integers(1, 9)))],
                       columns=["hadm_id", "icd_diagnosis"])
    icd = pd.concat([icd, icd.sample(max(1, len(icd) // 500), random_state=seed)])           # a few exact duplicates
    icd.to_csv(ext / "icd_diagnosis.csv", index=False)

    proc_cases = rng.choice(hadm, size=int(0.7 * n_cases), replace=False)
    proc = pd.DataFrame({"hadm_id": proc_cases, "icd_code": [f"P{int(rng.integers(10, 99))}" for _ in proc_cases],
                         "icd_title": "SYNTHETIC procedure", "icd_version": 10})
    pd.concat([proc, proc.sample(max(1, len(proc) // 30), random_state=seed)]).to_csv(ext / "icd_procedures.csv", index=False)
    dis = pd.DataFrame({"hadm_id": rng.choice(hadm, size=int(0.75 * n_cases), replace=False)})
    dis["discharge_procedure"] = "SYNTHETIC discharge procedure"
    dis.loc[0, "discharge_procedure"] = None                                                  # one empty value
    dis.to_csv(ext / "discharge_procedures.csv", index=False)

    rows = []
    for h in hadm:
        for itemid, label, unit, lo, hi in LABS:
            if rng.random() < 0.9:
                v = round(float(rng.normal((lo + hi) / 2, (hi - lo) / 2)), 1)
                text = f"{v} {unit}" if rng.random() > 0.08 else "NEG"
                has_range = rng.random() < 0.7
                rows.append((h, itemid, text, lo if has_range else np.nan, hi if has_range else np.nan))
    pd.DataFrame(rows, columns=["hadm_id", "itemid", "valuestr", "ref_range_lower", "ref_range_upper"]).to_csv(ext / "laboratory_tests.csv", index=False)
    mapping = pd.DataFrame([(float(i), n, "Blood", "Chemistry", 100.0, "[]") for i, n, *_ in LABS] + [(np.nan, "SYNTHETIC unmapped", None, None, None, "[]")],
                           columns=["itemid", "label", "fluid", "category", "count", "corresponding_ids"])
    mapping.to_csv(ext / "lab_test_mapping.csv", index=False)

    micro_cases = rng.choice(hadm, size=int(0.77 * n_cases), replace=False)
    pd.DataFrame({"hadm_id": micro_cases, "test_itemid": 90001, "valuestr": "NEGATIVE", "spec_itemid": 70001}).to_csv(ext / "microbiology.csv", index=False)
    rad = pd.DataFrame([(h, f"SYN-{h}-{k}", MODALITIES[int(rng.integers(0, 4))], "Abdomen", "SYNTHETIC EXAM", f"SYNTHETIC report text {k}.")
                        for h in hadm for k in range(int(rng.integers(1, 4)))],
                       columns=["hadm_id", "note_id", "modality", "region", "exam_name", "text"])
    rad.to_csv(ext / "radiology_reports.csv", index=False)

    adm = pd.DataFrame({"subject_id": [subject[int(h)] for h in hadm], "hadm_id": hadm, "admittime": "2100-01-01 00:00:00"})
    with gzip.open(hosp / "admissions.csv.gz", "wt") as fh:
        adm.to_csv(fh, index=False)

    (ext / "LICENSE.txt").write_text("SYNTHETIC DATA generated by clinverify.data.synthetic. Not MIMIC. No restrictions.\n")
    (out_dir / "SYNTHETIC").write_text("This folder holds synthetic data only.\n")
    for folder, names in [(ext, sorted(p.name for p in ext.iterdir() if p.name != "SHA256SUMS.txt")),
                          (hosp.parent, ["hosp/admissions.csv.gz"])]:
        (folder / "SHA256SUMS.txt").write_text("".join(f"{_sha(folder / n)}  {n}\n" for n in names))
    return out_dir
