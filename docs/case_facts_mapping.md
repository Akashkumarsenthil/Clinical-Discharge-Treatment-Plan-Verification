# Case facts: where each one comes from

The rule catalog (v2.0) checks a plan against **case facts** that describe the patient record, never the model's output (`CASE_FACTS` in `src/clinverify/plan.py`). Ext-CDM does not store them as fields, so `src/clinverify/data/case_facts.py` derives them from each admission's ICD diagnosis titles (`icd_diagnosis` table, joined on `hadm_id`).
The Ext-CDM cases were selected by primary ICD diagnosis (Hager et al. 2024, `papers/Hager2024_NatureMedicine.pdf`), so coded diagnoses are the most reliable source in the extract.

Every fact has three outcomes: **present** (an explicit title says so), **absent** (an explicit title says so, within what that title covers) or **unknown** (the fact is left out). A generic title ("Acute pancreatitis", "Unspecified acute appendicitis") or "without mention of hemorrhage" does not establish absence, so it never gives False. A rule that needs an unknown fact returns "insufficient information"; it never guesses.

## ICD structure used

| Condition | Code family (ICD-10-CM) | What the title tells us |
|---|---|---|
| Appendicitis | K35.2x generalized peritonitis, K35.3x localized peritonitis (also used for appendiceal abscess), K35.8x other or unspecified | peritonitis or abscess in the title means complicated |
| Pancreatitis | K85.x0 without necrosis or infection, K85.x1 with uninfected necrosis, K85.x2 with infected necrosis; K85.1x is biliary (gallstone) | necrosis, infection and biliary cause are in the title |
| Diverticulitis (large intestine) | K57.2x with perforation and abscess, K57.3x without perforation or abscess; the last digit says with or without bleeding | "with perforation" or "abscess" means complicated; "with bleeding" is an alarm symptom |

Sources: [AAPC, ICD-10 K codes for acute appendicitis](https://www.aapc.com/codes/coding-newsletters/my-internal-medicine-coding-alert/icd-10-k-codes-extract-more-details-for-acute-appendicitis-133085-article); [K85 acute pancreatitis](https://codebooks.rapidclaims.ai/icd10cm/K85) and [K85.02](https://icd-10codes.com/code/K85.02); [K57 group](https://www.findacode.com/icd-10-cm/icd-10-cm-diagnosis-codes-K57-group.html). These are reference sites, and one source set disagreed on the deeper K35 digits, so check titles against the CMS tabular list before relying on them for anything beyond this project.

## Mapping

| Fact | True when | False when | Otherwise | Used by |
|---|---|---|---|---|
| `complicated` (appendicitis) | a title has perforation, gangrene, abscess or generalized peritonitis | a title says "without perforation / gangrene / abscess" (for example K35.30) and none of those are present | unknown ("Unspecified acute appendicitis", "without mention of peritonitis") | R-APP-002, R-APP-003 |
| `complicated` (diverticulitis) | "with perforation", or a separate intestinal abscess, intestinal perforation or peritonitis code (attribution to the diverticulitis is assumed because it is the primary diagnosis) | "without perforation or abscess" and no separate complication code | unknown (ICD-9 "Diverticulitis of colon" alone) | R-DIV-001 to R-DIV-003 |
| `alarm_symptoms` | "with bleeding" or "with hemorrhage" on the diverticulitis title, GI or rectal hemorrhage, melena, hematochezia, iron-deficiency anemia, weight loss | never | unknown (absence of a code does not rule out symptoms; "without bleeding" and "without mention of hemorrhage" are not positives) | R-DIV-003 |
| `necrotizing` | "with uninfected necrosis" or "with infected necrosis" | "without necrosis or infection" (K85.x0) | unknown | R-PAN-002 |
| `infection` | "with infected necrosis" or a cholangitis diagnosis | "without necrosis or infection" and no infection-type diagnosis coded anywhere (sepsis, pneumonia, abscess, peritonitis, urinary tract and similar) | unknown | R-PAN-001, R-PAN-002 |
| `biliary` | "biliary acute pancreatitis" or "gallstone pancreatitis" | another cause is named (idiopathic, alcohol-induced, drug-induced, other acute pancreatitis) | unknown (generic "Acute pancreatitis", older ICD-9 codes) | R-PAN-003, R-PAN-004 |
| `cholangitis` | a cholangitis diagnosis | not coded (diagnoses are coded when present; sensitivity is limited) | never unknown | R-PAN-004 |
| `biliary_obstruction` | "obstruction of bile duct" or a bile-duct stone title with obstruction | not coded (same caveat) | never unknown | R-PAN-004 |
| `mild` | an explicit "without necrosis or infection" title and no organ failure coded | necrosis coded, or organ failure coded (shock, respiratory or kidney failure, severe sepsis) | unknown (codes cannot show the absence of organ failure; Atlanta classification) | R-PAN-003 |
| `oral_or_enteral_feasible`, `low_risk`, `crc_screening_up_to_date` | never derived | never derived | always unknown (no field or code in the record) | R-PAN-005, R-DIV-001, R-DIV-003 |

For the last row, the matching rules stay "insufficient information" on real cases. That is correct behavior. If the team wants those rules to run, supply the fact by another route and add it to `derive_facts`.

## Results on the real data (counts only, 2,400 cases)

Produced by `python scripts/case_facts_counts.py`; saved in `docs/case_facts_counts.csv` (counts only, no patient text). The 100-test-case counts are in the CSV.

| Pathology | Fact | True | False | Unknown | Cases |
|---|---|---|---|---|---|
| appendicitis | complicated | 221 | 1 | 735 | 957 |
| diverticulitis | complicated | 93 | 36 | 128 | 257 |
| diverticulitis | alarm_symptoms | 14 | 0 | 243 | 257 |
| pancreatitis | necrotizing | 7 | 89 | 442 | 538 |
| pancreatitis | infection | 38 | 54 | 446 | 538 |
| pancreatitis | biliary | 69 | 24 | 445 | 538 |
| pancreatitis | cholangitis | 37 | 501 | 0 | 538 |
| pancreatitis | biliary_obstruction | 86 | 452 | 0 | 538 |
| pancreatitis | mild | 59 | 108 | 371 | 538 |

What the checks found (version history):
- Appendicitis "complicated" was 78% when any peritonitis counted; counting only perforation, gangrene, abscess or generalized peritonitis gave 23% of cases, in line with published rates.
- A review found four further problems, all fixed with regression tests: generic titles were treated as "absent"; `mild` pancreatitis was inferred from missing words; "without mention of hemorrhage" wrongly counted as an alarm symptom (alarm symptoms fell from 174 to 14 cases); and "Generalized (acute) peritonitis" was missed for diverticulitis.

**Consequence:** most appendicitis cases (735 of 957) have no complication status in the coded diagnoses, so R-APP-002 and R-APP-003 return "insufficient information" for them. That is honest, but it limits what the benchmark can test. To raise coverage, add the discharge diagnosis text or MIMIC-IV `diagnoses_icd` codes with version as extra evidence (planned).

## How to check it on the real data (locally only)

Run the derivation over the cases and look at **counts only**, such as "complicated appendicitis: 41 of 100". Do not paste patient text into chat tools or commit the per-case table. The synthetic tests in `tests/test_case_facts.py` use public ICD title wording only.
