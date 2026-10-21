# Split leakage check (patient level)

The first split (v1) divided cases by admission ID (`hadm_id`). One patient can have several admissions, so `scripts/patient_overlap_check.py` maps each admission to its patient (`subject_id`, from MIMIC-IV `admissions`) and looks for patients present in more than one split.

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

## Fix: split v2 (grouped by patient)

`data/splits/ext_cdm_splits_v2.json` is built by `make_grouped_splits` in `src/clinverify/data/splits.py`: stratified by pathology, seed 298, and every admission of a patient goes to the same split. v1 (split by admission only) has been removed from the repository so there is one authoritative split; its result is recorded in the table below and it can be rebuilt with `make_splits`.

| Check | v1 (by admission) | v2 (grouped by patient) |
|---|---|---|
| Sizes train / val / test | 1,840 / 460 / 100 | 1,840 / 460 / 100 |
| Test class mix (appendicitis / cholecystitis / pancreatitis / diverticulitis) | 40 / 27 / 22 / 11 | 40 / 27 / 22 / 11 |
| Admission IDs shared between splits | 0 | 0 |
| Patients in more than one split | 5 | **0** |
| Reproducible with the same seed | yes | yes |

Verify with `python scripts/patient_overlap_check.py` (checks every `ext_cdm_splits_v*.json` file present) and `python -m pytest tests`.

## Decision to record

v2 is the split used by the project (the notebook and `scripts/data_demo.py` now build and save v2). The change must be stated in Workbook 2 section 3.5, and the 100-case held-out test set is now the v2 test set (5 of its cases differ from v1's).
