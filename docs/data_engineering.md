# Data engineering (report Section 3)

Project documentation of the data pipeline, organised like Section 3 of the project report template. Code: `scripts/data_demo.py`, `src/clinverify/data/`; walk-through: `notebooks/data_pipeline_demo.ipynb`. Run end to end with `python scripts/data_demo.py all`.
No patient text appears here; only counts and aggregates.

## 3.1 Data process

```
download + SHA256 check -> link check -> cleaning (duplicates, missing values) -> transformations
  -> validation checks -> exploratory analysis -> patient-grouped, pathology-stratified splits
```

| Stage | Output | Where |
|---|---|---|
| Raw data | MIMIC-IV v3.1 and MIMIC-IV-Ext-CDM v1.1 | `~/data/mimic/` (outside the repo, never committed) |
| Cleaned and transformed tables | in memory only | patient files are never written into the repo |
| Splits | case IDs only | `data/splits/ext_cdm_splits_v2.json` |
| Aggregate results | counts, figures | `results/`, `docs/images/` |

## 3.2 Data collection

| Item | Value |
|---|---|
| Sources | MIMIC-IV v3.1 (about 9.9 GB) and MIMIC-IV-Ext-CDM v1.1 (17 MB) from PhysioNet |
| Size | 2,400 curated cases across four abdominal pathologies (appendicitis, cholecystitis, pancreatitis, diverticulitis) |
| Access | PhysioNet credentialed access and signed data use agreement, per person; data is not shared |
| Integrity | every file matches `SHA256SUMS.txt`: MIMIC-IV 33 of 33, Ext-CDM 12 of 12 |
| Link check | all 2,400 `hadm_id` values exist in MIMIC-IV `admissions` (546,028 admissions) |
| Tables per case | history of present illness, physical examination, laboratory tests, radiology reports, ICD diagnoses, discharge diagnosis, discharge procedures |
| Limits | credentialed licence: no sharing or re-identification; MIMIC text is not sent to hosted LLM APIs |

Steps and commands: `docs/data_collection.md`. Field definitions: `docs/data_dictionary.md`.

## 3.3 Data pre-processing

- **Duplicates:** exact duplicate rows removed, 75 in total (before and after counts per table from `step_clean`).
- **Missing values:** one rule per column (`MISSING_RULES` in `ext_cdm.py`). Rows that cannot be joined or have an empty procedure are dropped. Missing lab reference ranges are kept as missing and flagged `unknown`, never imputed, because reference ranges are lab-specific facts.
- **Validation checks:** `validate_tables` passes on the cleaned data and fails on a deliberately corrupted copy, which shows the checks detect real problems.

## 3.4 Data transformation

| Table | Input | Operation | Output | Why |
|---|---|---|---|---|
| text tables (HPI, exam, radiology, discharge dx) | raw free text | strip, collapse whitespace, cast to str | normalised text + word count | consistent format; length as a simple input-size feature |
| laboratory_tests | `valuestr` (e.g. "2.5 mmol/L") | split into number, unit and `<`/`>` qualifier; non-numeric results stay text | value, unit, qualifier, `value_is_numeric` | numeric comparison with the reference range |
| laboratory_tests | value, reference range | flag low / normal / high; `unknown` if range missing | `flag` | abnormal-only views; no invented ranges |
| lab_test_mapping | `itemid` | drop rows without it, cast to int | `itemid`, `label` | readable lab names on each lab row |
| all case tables | `hadm_id` + `pathology_ids.json` | join pathology label | `cases_master` | label for stratified splits and per-class EDA |

## 3.5 Data preparation

| Split | Cases |
|---|---|
| train | 1,840 |
| validation | 460 |
| test (held out) | 100 |

- Seed 298, stratified by pathology, grouped by patient (`subject_id`): every admission of a patient goes to one split. Reproducible with the same seed; stored as IDs only and versioned in git.
- **Leakage checks:** admission-level (no `hadm_id` in two splits) and patient-level (no patient in two splits). Both pass on v2; a deliberately leaky split is caught.
- **What was found:** the first split (by admission) had 0 shared admissions but 5 patients in two splits, one in the test set. Split v2 fixed this (0 patients in more than one split). Details: `docs/split_leakage_check.md`.
- The 100-case test set is not used for tuning rules or models.

## 3.6 Data statistics

- Class imbalance: appendicitis 957 vs diverticulitis 257 (3.7x), so per-class results are reported next to overall ones.
- About 29% of lab rows have no usable reference range (kept as `unknown`); 28.2% of flaggable lab results are abnormal.
- Per-case size (mean): 57.8 lab rows, 2.5 radiology reports, 7.2 ICD diagnoses, 172 HPI words.
- Figure: `docs/images/eda_overview.png`.
- **Coverage gap:** all cases come from one hospital system (Beth Israel Deaconess Medical Center, MIMIC-IV) and four abdominal diagnoses, so findings may not transfer to other hospitals, populations or conditions. Patients from other care settings would be the least represented if the system were deployed.
