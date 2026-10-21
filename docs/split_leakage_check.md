# Split leakage check (patient level)

`data/splits/ext_cdm_splits_v1.json` splits by admission ID (`hadm_id`). One patient can have several admissions, so `scripts/patient_overlap_check.py` maps each admission to its patient (`subject_id`, from MIMIC-IV `admissions`) and looks for patients present in more than one split.

## Result on split v1 (seed 298; 1,840 train / 460 val / 100 test)

| Check | Result |
|---|---|
| Admission IDs shared between splits | 0 (PASS) |
| Distinct patients among the 2,400 cases | 2,383 |
| Cases that share a patient with another case | 34 |
| Patients in both train and val | 4 |
| Patients in both train and test | 1 |
| Patients in both val and test | 0 |
| **Patient-level check** | **FAIL: 5 patients cross splits** |

## What it means

Admission-level leakage is zero, but 5 patients appear in two splits (one of them in the held-out test set). The effect is small, yet a held-out set should contain no patient seen in training.

## Options (team decision; the split is meant to stay fixed)

1. Keep v1 and report this limitation next to the results.
2. Create `ext_cdm_splits_v2.json` that groups all admissions of a patient into the same split (stratified by pathology), and state the change in Workbook 2 section 3.5.

Option 2 changes a "fixed" artifact, so it needs the team's agreement and a note in the report.
