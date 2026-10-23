# Case facts: where each one comes from

The rule catalog (v2.0) checks a plan against **case facts** that describe the patient record, never the model's output (`CASE_FACTS` in `src/clinverify/plan.py`). Ext-CDM does not store them as fields, so `src/clinverify/data/case_facts.py` derives them from each admission's ICD diagnosis titles (`icd_diagnosis` table, joined on `hadm_id`).
The Ext-CDM cases were selected by primary ICD diagnosis (Hager et al. 2024, `papers/Hager2024_NatureMedicine.pdf`), so coded diagnoses are the most reliable source in the extract.

A fact the record cannot support is **left out**, so the verifier reports "insufficient information" for the rules that need it. It never guesses.

## ICD structure used

| Condition | Code family (ICD-10-CM) | What the title tells us |
|---|---|---|
| Appendicitis | K35.2x generalized peritonitis, K35.3x localized peritonitis (also used for appendiceal abscess), K35.8x other or unspecified | peritonitis or abscess in the title means complicated |
| Pancreatitis | K85.x0 without necrosis or infection, K85.x1 with uninfected necrosis, K85.x2 with infected necrosis; K85.1x is biliary (gallstone) | necrosis, infection and biliary cause are in the title |
| Diverticulitis (large intestine) | K57.2x with perforation and abscess, K57.3x without perforation or abscess; the last digit says with or without bleeding | "with perforation" or "abscess" means complicated; "with bleeding" is an alarm symptom |

Sources: [AAPC, ICD-10 K codes for acute appendicitis](https://www.aapc.com/codes/coding-newsletters/my-internal-medicine-coding-alert/icd-10-k-codes-extract-more-details-for-acute-appendicitis-133085-article); [K85 acute pancreatitis](https://codebooks.rapidclaims.ai/icd10cm/K85) and [K85.02](https://icd-10codes.com/code/K85.02); [K57 group](https://www.findacode.com/icd-10-cm/icd-10-cm-diagnosis-codes-K57-group.html). These are reference sites, and one source set disagreed on the deeper K35 digits, so check titles against the CMS tabular list before relying on them for anything beyond this project.

## Mapping

| Fact | Rule | Used by | Derivable |
|---|---|---|---|
| `complicated` (appendicitis) | any appendicitis title with perforation, gangrene, abscess or generalized peritonitis (localized peritonitis "without perforation or gangrene", K35.30, is not complicated) | R-APP-002, R-APP-003 | yes |
| `complicated` (diverticulitis) | bowel title with "with perforation", abscess or peritonitis (and not "without perforation") | R-DIV-001 to R-DIV-003 | yes |
| `necrotizing` | pancreatitis title "with uninfected necrosis" or "with infected necrosis" | R-PAN-002 | yes |
| `infection` | pancreatitis "with infected necrosis", or a cholangitis diagnosis | R-PAN-001, R-PAN-002 | partly: other infections (for example pneumonia) are not checked |
| `biliary` | "biliary acute pancreatitis" or "gallstone pancreatitis" | R-PAN-003, R-PAN-004 | partly: gallstone pancreatitis coded only as another cause is missed |
| `cholangitis` | any cholangitis title | R-PAN-004 | yes |
| `biliary_obstruction` | "obstruction of bile duct" or a bile-duct stone title with obstruction | R-PAN-004 | yes |
| `mild` | no necrosis and no coded organ failure (shock, respiratory or kidney failure, severe sepsis) | R-PAN-003 | approximate: no ICU or severity score in the extract |
| `alarm_symptoms` | "with bleeding", GI or rectal hemorrhage, iron-deficiency anemia, weight loss | R-DIV-003 | approximate: symptoms only in notes are missed |
| `oral_or_enteral_feasible` | none | R-PAN-005 | **no**: needs diet orders or nursing notes |
| `low_risk` | none | R-DIV-001 | **no**: needs comorbidity and immune status |
| `crc_screening_up_to_date` | none | R-DIV-003 | **no**: screening history is not in the record |

For the three that cannot be derived, the matching rules stay "insufficient information" on real cases. That is correct behavior. If the team wants those rules to run, supply the fact by another route (for example from MIMIC-IV `poe` for diet orders) and add it to `derive_facts`.

## Results on the real data (counts only, 2,400 cases)

Produced by `python scripts/case_facts_counts.py`; saved in `docs/case_facts_counts.csv` (counts only, no patient text). Every case matched a diagnosis title for its pathology except cholecystitis, which the rules do not cover.

| Pathology | Fact | True | False | Cases |
|---|---|---|---|---|
| appendicitis | complicated | 221 | 736 | 957 |
| diverticulitis | complicated | 96 | 161 | 257 |
| diverticulitis | alarm_symptoms | 174 | 83 | 257 |
| pancreatitis | necrotizing | 7 | 531 | 538 |
| pancreatitis | infection | 38 | 500 | 538 |
| pancreatitis | biliary | 69 | 469 | 538 |
| pancreatitis | cholangitis | 37 | 501 | 538 |
| pancreatitis | biliary_obstruction | 86 | 452 | 538 |
| pancreatitis | mild | 430 | 108 | 538 |

Check made on the first run: appendicitis "complicated" was 78%, too high, because localized peritonitis without perforation was counted. After the fix it is 23%, in line with published rates. `biliary` (13%) is probably an undercount, since gallstone pancreatitis is often coded as a gallstone code next to a generic pancreatitis code; a co-occurrence rule could be added if the team wants it.

## How to check it on the real data (locally only)

Run the derivation over the cases and look at **counts only**, such as "complicated appendicitis: 41 of 100". Do not paste patient text into chat tools or commit the per-case table. The synthetic tests in `tests/test_case_facts.py` use public ICD title wording only.
