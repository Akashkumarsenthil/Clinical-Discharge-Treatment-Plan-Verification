# Data dictionary

Tables and columns used or considered by the project. Generated from the file headers (no patient values). Source datasets: MIMIC-IV v3.1 and MIMIC-IV-Ext-CDM v1.1 (credentialed PhysioNet data, not stored in this repository).

## MIMIC-IV-Ext-CDM v1.1 (working set: 2,400 cases)

`hadm_id` (hospital admission ID) links every table; `pathology_ids.json` maps each `hadm_id` to its pathology (appendicitis 957, cholecystitis 648, pancreatitis 538, diverticulitis 257).

| Table | Rows | Columns (type) |
|---|---|---|
| `history_of_present_illness` | 2,400 | `hadm_id` (int64), `hpi` (text) |
| `physical_examination` | 2,400 | `hadm_id` (int64), `pe` (text) |
| `discharge_diagnosis` | 2,400 | `hadm_id` (int64), `discharge_diagnosis` (text) |
| `icd_diagnosis` | 17,357 | `hadm_id` (int64), `icd_diagnosis` (text) |
| `icd_procedures` | 2,917 | `hadm_id` (int64), `icd_code` (text), `icd_title` (text), `icd_version` (int64) |
| `discharge_procedures` | 2,122 | `hadm_id` (int64), `discharge_procedure` (text) |
| `laboratory_tests` | 138,788 | `hadm_id` (int64), `itemid` (int64), `valuestr` (text), `ref_range_lower` (float64), `ref_range_upper` (float64) |
| `lab_test_mapping` | 1,209 | `itemid` (float64), `label` (text), `fluid` (text), `category` (text), `count` (float64), `corresponding_ids` (text) |
| `microbiology` | 4,403 | `hadm_id` (int64), `test_itemid` (int64), `valuestr` (text), `spec_itemid` (int64) |
| `radiology_reports` | 5,960 | `hadm_id` (int64), `note_id` (text), `modality` (text), `region` (text), `exam_name` (text), `text` (text) |

## MIMIC-IV v3.1 tables that can supply fields Ext-CDM lacks

Some proposed rules need medication orders or event timestamps, which Ext-CDM does not contain. These MIMIC-IV tables do; they link to Ext-CDM through `hadm_id` (all 2,400 cases are present in `admissions`).

| Table | Module | Columns | Possible use |
|---|---|---|---|
| `admissions` | hosp | `subject_id`, `hadm_id`, `admittime`, `dischtime`, `deathtime`, `admission_type`, `admit_provider_id`, `admission_location`, `discharge_location`, `insurance`, `language`, `marital_status`, `race`, `edregtime`, `edouttime`, `hospital_expire_flag` | admit/discharge times and discharge location |
| `patients` | hosp | `subject_id`, `gender`, `anchor_age`, `anchor_year`, `anchor_year_group`, `dod` | age, gender (patient-level split check via `subject_id`) |
| `labevents` | hosp | `labevent_id`, `subject_id`, `hadm_id`, `specimen_id`, `itemid`, `order_provider_id`, `charttime`, `storetime`, `value`, `valuenum`, `valueuom`, `ref_range_lower`, `ref_range_upper`, `flag`, `priority`, `comments` | lab results with timestamps (labs before discharge) |
| `prescriptions` | hosp | `subject_id`, `hadm_id`, `pharmacy_id`, `poe_id`, `poe_seq`, `order_provider_id`, `starttime`, `stoptime`, `drug_type`, `drug`, `formulary_drug_cd`, `gsn`, `ndc`, `prod_strength`, `form_rx`, `dose_val_rx`, `dose_unit_rx`, `form_val_disp`, `form_unit_disp`, `doses_per_24_hrs`, `route` | medication orders (contraindication rules) |
| `pharmacy` | hosp | `subject_id`, `hadm_id`, `pharmacy_id`, `poe_id`, `starttime`, `stoptime`, `medication`, `proc_type`, `status`, `entertime`, `verifiedtime`, `route`, `frequency`, `disp_sched`, `infusion_type`, `sliding_scale`, `lockout_interval`, `basal_rate`, `one_hr_max`, `doses_per_24_hrs`, `duration`, `duration_interval`, `expiration_value`, `expiration_unit`, `expirationdate`, `dispensation`, `fill_quantity` | medication dispensing detail |
| `poe` | hosp | `poe_id`, `poe_seq`, `subject_id`, `hadm_id`, `ordertime`, `order_type`, `order_subtype`, `transaction_type`, `discontinue_of_poe_id`, `discontinued_by_poe_id`, `order_provider_id`, `order_status` | provider orders |
| `emar` | hosp | `subject_id`, `hadm_id`, `emar_id`, `emar_seq`, `poe_id`, `pharmacy_id`, `enter_provider_id`, `charttime`, `medication`, `event_txt`, `scheduletime`, `storetime` | medication administration |
| `transfers` | hosp | `subject_id`, `hadm_id`, `transfer_id`, `eventtype`, `careunit`, `intime`, `outtime` | ward movements and timing |
| `services` | hosp | `subject_id`, `hadm_id`, `transfertime`, `prev_service`, `curr_service` | treating service |
| `diagnoses_icd` | hosp | `subject_id`, `hadm_id`, `seq_num`, `icd_code`, `icd_version` | coded diagnoses |
| `procedures_icd` | hosp | `subject_id`, `hadm_id`, `seq_num`, `chartdate`, `icd_code`, `icd_version` | coded procedures |

Regenerate this file from the headers if the dataset version changes.
