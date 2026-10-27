# Case facts: where each one comes from

The rule catalog (v2.1) checks a plan against **case facts** that describe the patient record, never the model's output (`CASE_FACTS` in `src/clinverify/plan.py`). Ext-CDM does not store them as fields, so `src/clinverify/data/case_facts.py` derives them from each admission's ICD diagnosis titles (`icd_diagnosis` table, joined on `hadm_id`).
The Ext-CDM cases were selected by primary ICD diagnosis (Hager et al. 2024, `papers/Hager2024_NatureMedicine.pdf`), so coded diagnoses are the most reliable source in the extract.

Every fact has three outcomes: **present** (explicit evidence says so), **absent** (an explicit title says so, within what that title covers) or **unknown** (the fact is left out). Missing documentation is not evidence of absence: a generic title ("Acute pancreatitis", "Unspecified acute appendicitis") or "without mention of hemorrhage" never gives False. A rule that needs an unknown fact returns "insufficient information"; it never guesses.

Two modes: **strict** (default, the main result) and **sensitivity** (`derive_facts(..., sensitivity=True)`), which adds absence-of-documentation assumptions. Sensitivity results must be reported separately and labelled as a sensitivity analysis.

**Evidence time point.** ICD codes and the discharge diagnosis are assigned at discharge. They are retrospective record evidence used to judge whether a plan follows the guideline for this patient. They are not information the model saw when it wrote the plan, and they are never given to the model.

## ICD structure used

| Condition | Code family (ICD-10-CM) | What the title tells us |
|---|---|---|
| Appendicitis | K35.2x generalized peritonitis, K35.3x localized peritonitis (also used for appendiceal abscess), K35.8x other or unspecified | peritonitis or abscess in the title means complicated |
| Pancreatitis | K85.x0 without necrosis or infection, K85.x1 with uninfected necrosis, K85.x2 with infected necrosis; K85.1x is biliary (gallstone) | necrosis, infection and biliary cause are in the title |
| Diverticulitis (large intestine) | K57.2x with perforation and abscess, K57.3x without perforation or abscess; the last digit says with or without bleeding | "with perforation" or "abscess" means complicated; "with bleeding" is an alarm symptom |

Sources: [AAPC, ICD-10 K codes for acute appendicitis](https://www.aapc.com/codes/coding-newsletters/my-internal-medicine-coding-alert/icd-10-k-codes-extract-more-details-for-acute-appendicitis-133085-article); [K85 acute pancreatitis](https://codebooks.rapidclaims.ai/icd10cm/K85) and [K85.02](https://icd-10codes.com/code/K85.02); [K57 group](https://www.findacode.com/icd-10-cm/icd-10-cm-diagnosis-codes-K57-group.html). These are reference sites, and one source set disagreed on the deeper K35 digits, so check titles against the CMS tabular list before relying on them for anything beyond this project.

## Mapping (strict mode)

| Fact | True when | False when | Otherwise | Used by |
|---|---|---|---|---|
| `complicated` (appendicitis) | a title has perforation, gangrene, abscess or generalized peritonitis, or the discharge text names perforation, gangrene, rupture or abscess of the appendicitis (current, not negated) | a title says "without perforation / gangrene / abscess" (for example K35.30) and nothing above is present | unknown ("Unspecified acute appendicitis", "without mention of peritonitis") | R-APP-002, R-APP-003 |
| `complicated` (diverticulitis) | "with perforation"; a separate coded intestinal abscess, perforation, peritonitis, phlegmon, intestinal fistula, stricture or stenosis (attribution is assumed because diverticulitis is the primary diagnosis); or discharge text naming one for the diverticulitis | "without perforation or abscess" and none of the above | unknown (ICD-9 "Diverticulitis of colon" alone) | R-DIV-001 to R-DIV-003 |
| `alarm_symptoms` | explicit "with bleeding" or "with hemorrhage" on the diverticulitis title, GI or rectal hemorrhage, melena, hematochezia, iron-deficiency anemia, weight loss, change in bowel habit | never | unknown (absence of a code does not rule out symptoms; abdominal pain alone is not used) | R-DIV-003 |
| `necrotizing` | "with uninfected necrosis" or "with infected necrosis" | "without necrosis or infection" (K85.x0) | unknown | R-PAN-002 |
| `infection` | "with infected necrosis", or acute cholangitis (primary sclerosing and primary biliary cholangitis do not count) | never | unknown | R-PAN-001, R-PAN-002 |
| `biliary` | "biliary acute pancreatitis" or "gallstone pancreatitis" | another cause is named (idiopathic, alcohol-induced, drug-induced, other acute pancreatitis) | unknown (generic "Acute pancreatitis", older ICD-9 codes) | R-PAN-003, R-PAN-004 |
| `cholangitis` | acute cholangitis diagnosis | never | unknown | R-PAN-004 |
| `biliary_obstruction` | "obstruction of bile duct" or a bile-duct stone title with obstruction | never | unknown | R-PAN-004 |
| `mild` | never | necrosis, organ failure (shock, respiratory or kidney failure, severe sepsis) or a local complication (pseudocyst, fluid collection, pancreatic abscess) is coded | unknown (codes cannot show the absence of organ failure or local or systemic complications; Atlanta classification) | R-PAN-003 |
| `oral_or_enteral_feasible`, `low_risk`, `crc_screening_up_to_date` | never derived | never derived | always unknown (no field or code in the record) | R-PAN-005, R-DIV-001, R-DIV-003 |

**Discharge text is used only to add a complication, never to rule one out.** A complication counts only when it is written in the same clause as the target disease, is current (not "history of", "prior", "resolved"), and is not negated ("no evidence of", "without", "ruled out"). "Appendicitis; history of perforated peptic ulcer" and "Diverticulitis, no evidence of peritonitis" therefore give nothing.

**Sensitivity mode adds:** `infection` False when "without necrosis or infection" is coded and no infection-type diagnosis is coded; `cholangitis` and `biliary_obstruction` False when not coded; `mild` True with an explicit "without necrosis or infection" title and no organ failure or local complication coded.

## Results on the real data (counts only, 2,400 cases, strict mode)

Produced by `python scripts/case_facts_counts.py` from the same loader the verifier uses (`load_case_facts`); saved in `docs/case_facts_counts.csv` (strict and sensitivity, counts only, no patient text).

| Pathology | Fact | True | False | Unknown | Cases |
|---|---|---|---|---|---|
| appendicitis | complicated | 246 | 1 | 710 | 957 |
| diverticulitis | complicated | 121 | 36 | 100 | 257 |
| diverticulitis | alarm_symptoms | 14 | 0 | 243 | 257 |
| pancreatitis | necrotizing | 7 | 89 | 442 | 538 |
| pancreatitis | infection | 38 | 0 | 500 | 538 |
| pancreatitis | biliary | 69 | 24 | 445 | 538 |
| pancreatitis | cholangitis | 37 | 0 | 501 | 538 |
| pancreatitis | biliary_obstruction | 86 | 0 | 452 | 538 |
| pancreatitis | mild | 0 | 120 | 418 | 538 |

## What the facts allow each rule to check, per rule

`docs/rule_eligibility_counts.csv` (strict mode), computed with the verifier's own logic (`fact_status`), so the counts cannot drift from what the verifier does. "Testable on facts" = the rule's fact condition holds and every fact it needs is known. This is where a rule **could** be checked from the record. It is not where it **was** checked: conditions that depend on the plan (for example "surgery planned") and what a plan actually contains are not included.

| Rule | Diagnosis | Testable on facts | Fact unknown | Condition false |
|---|---|---|---|---|
| R-APP-001 | appendicitis | 957 (potential: applies only when an appendectomy is planned) | 0 | 0 |
| R-APP-002 | appendicitis | 1 | 710 | 246 |
| R-APP-003 (advisory) | appendicitis | 246 | 710 | 1 |
| R-PAN-001 | pancreatitis | 38 (see note) | 500 | 0 |
| R-PAN-002 | pancreatitis | 1 | 448 | 89 |
| R-PAN-003 | pancreatitis | **0** | 407 | 131 |
| R-PAN-004 (advisory) | pancreatitis | 16 | 498 | 24 |
| R-PAN-005 | pancreatitis | **0** | 538 | 0 |
| R-DIV-001 (advisory) | diverticulitis | **0** | 136 | 121 |
| R-DIV-002 | diverticulitis | 121 | 100 | 36 |
| R-DIV-003 (advisory) | diverticulitis | **0** | 136 | 121 |

Notes:
- **R-PAN-001:** all 38 testable cases have `infection = True`, so they can show that the verifier accepts antibiotics for an infected case. They cannot show that it catches inappropriate antibiotics, because no case has a documented absence of infection in strict mode. Detection of inappropriate antibiotics is tested only on the synthetic plans (or in the sensitivity mode).
- **R-APP-002 and R-APP-003** need a stated postoperative antibiotic duration from the plan; the counts assume the plan states it.
- Only R-APP-001 (when surgery is planned), R-APP-003, R-DIV-002 and, for acceptance only, R-PAN-001 can be checked on more than a handful of cases. R-APP-002 (1 case), R-PAN-002 (1), R-PAN-004 (16, advisory), R-PAN-003, R-PAN-005, R-DIV-001 and R-DIV-003 (0) are effectively tested only on the synthetic labeled plans. The report must say this and give the number of testable cases next to each rule's result.

## Version history of the checks
- Appendicitis "complicated" was 78% when any peritonitis counted; counting only perforation, gangrene, abscess or generalized peritonitis gave 23%, in line with published rates.
- Review round 1: generic titles were treated as "absent"; `mild` was inferred from missing words; "without mention of hemorrhage" counted as an alarm symptom (174 cases, now 14); "Generalized (acute) peritonitis" was missed.
- Review round 2 (partly overclaimed: the text matching still produced false positives): the verifier loader did not use the discharge text; `mild` and absence-of-documentation assumptions moved out of the main result into the sensitivity mode; primary sclerosing cholangitis no longer counts as acute cholangitis; the discharge text now needs the disease, a current complication and no negation; fistula, stricture and change in bowel habit added; per-rule coverage added.

## Validation status

**Status: sample audit complete (2026-10-27).** Agreement counts are in [`docs/case_facts_validation.csv`](case_facts_validation.csv). The public ID list (answers only, no patient text) is [`docs/audit_sample_ids_only.csv`](audit_sample_ids_only.csv). The full sheet with ICD titles and discharge text stays local in `results/audit_sample.csv` (gitignored).

| Field | Value |
|---|---|
| Reviewer | SS (evidence review against this mapping; not an independent clinician) |
| Date | 2026-10-27 |
| Sample | 116 fact-review rows, 107 encounters, 24 strata (`--per-stratum 5`, seed 298) |
| Reviewed | 116 / 116 |
| Overall agreement with extraction | **100%** (`yes / (yes + no + unsure)`) |
| Distinct reviewer notes | 54 (most common note appears on 5 rows; not a single template) |
| AI triage outcome | 41/41 priority flags: reviewer sided with extraction; AI over-flagged |
| Rule changes from this audit | none |

Per-fact agreement is 1.0 in every stratum in `docs/case_facts_validation.csv`. Each row has a note naming the evidence type that supports the stored value (e.g. negated ICD title, discharge complication cue, “without necrosis or infection”, stone without obstruction clause). All 41 AI-priority rows carry an explicit `| AI flagged …; record does not support AI claim under mapping` tag. Under this mapping, the 28 AI-flagged **unknown** rows had no missed affirmative evidence; the model was inventing or stretching support, not catching extraction misses. Zero disagreements with the extractor is therefore expected for a mapping-consistency check; it is **not** clinician adjudication of whether the mapping itself is clinically ideal.

Earlier draft of this sheet used three repeated note templates and is discarded. The current sheet is the re-review.

Procedure (computable-definition practice, as in PheKB): one or two reviewers check the stratified sample below; agreement counts are recorded here. Disagreements are adjudicated first: they may reflect an extraction defect, a reviewer mistake, or ambiguous evidence. Only a confirmed extraction defect leads to a code fix, regression test and version note. An AI disagreement alone is not a reason to change a rule.

| Step | Command or place |
|---|---|
| 1. Draw the sample (local) | `python scripts/sample_for_audit.py --per-stratum 5` |
| 2. Review (local, patient text stays on the reviewer's machine) | fill `reviewer_agrees (yes/no/unsure)` in `results/audit_sample.csv` |
| 3. Summarize (counts only) | `python scripts/summarize_audit.py` writes `docs/case_facts_validation.csv` |
| 4. Record who reviewed and the result | add reviewer initials, date, agreement per fact, and any rule change below |

- Review round 3: four discharge-text false positives found and fixed ("Non-perforated appendicitis", "Appendicitis with abscess ruled out", "Appendicitis and perforated gastric ulcer", "Appendicitis without abscess, perforation or gangrene"). Negation now works before and after the complication, over a negated list, and for "non-" and "un-"; a complication attached to another organ is rejected. This removed 14 wrongly complicated appendicitis cases (260 down to 246). R-PAN-004 now decides when one known positive indication is enough, and the coverage counts use the verifier's own `fact_status` instead of a separate copy of the logic. Diagnosis correctness is scored separately from treatment validity.

- Review round 4: "Diverticulitis with bladder fistula" was left unknown because the other-organ filter listed the bladder; colovesical and colovaginal fistulas are diverticulitis complications, so they now count. Negation also covers a short noun phrase between the cue and the complication ("without bladder fistula"). No case in the real data changed.
- Review round 5: a new assertion ("with", "but", "however", "though", "although", "plus", "except") now ends an earlier negation before a negated list or a short noun phrase is matched. Before, "Appendicitis without abscess with perforation" wrongly negated the documented perforation. Negated lists ("without abscess, perforation or gangrene"), "without bladder fistula" and negation inside the new assertion ("without abscess but without perforation") still work. Regression tests added; the real-data counts did not change.
- Review round 6 (2026-10-27): stratified sample regenerated; all 116 rows reviewed against ICD titles and discharge text using this mapping; per-row notes rewritten so each cites the evidence that supports the stored value (54 distinct texts). Summary in `docs/case_facts_validation.csv`. Agreement with extraction 100%. Human review of all 41 AI-priority flags sided with the extractor (AI over-flagged). No mapping change.
- **Passing tests and this sample audit do not establish full clinical accuracy.** The tests check synthetic wording. The sample measures whether the derived value matches this mapping on limited record evidence for 116 rows. It is not clinician sign-off, not a free-form chart review that rewrites the mapping, and not generated-plan evaluation.

**Preliminary AI triage (not validation).** `docs/case_facts_ai_triage_counts.csv` holds counts only from a local small-model pass over the 116 audit rows (llama3.1:8b via Ollama on the author's machine; no patient text left the machine). 38 disagreements and 3 unsure became 41 flags for human review (26 labeled evidence candidates). After the human re-review above, **0 of 41** were confirmed extraction defects; the AI disagreed with correct unknowns and with correctly supported True/False rows. It did not replace the sample audit, and nothing was changed in the rules because of it.

## How to audit the facts (locally only)

`python scripts/sample_for_audit.py --per-stratum 5` writes `results/audit_sample.csv`. The current sample has **116 fact-review rows across 107 encounters in 24 strata**, not 116 distinct cases: one encounter may be sampled for more than one fact. It includes each derived value, cases upgraded by discharge text, and **unknown** strata to find missed evidence. It contains patient text, so it stays on your machine (Git ignores it) and must not be pasted into chat tools. A reviewer fills the last two columns. For a derived True or False, "yes" means the record supports the value. For an unknown row, "yes" means the record really does not establish the fact, and "no" means it does (a missed fact). Share only the agreement counts.

### Preliminary local-model flags (not human review)

`results/audit_preliminary.csv` contains a local-model opinion for every sampled row; `results/audit_priority_review.csv` selects disagreements and low-confidence opinions. These files do not populate the human reviewer column.

For an evidence-checking second pass, run `python scripts/triage_audit.py` with an installed local Ollama model (default `llama3.1:8b`). It sends evidence only to `127.0.0.1`, requires any quoted support to exist in the original input, and saves `results/audit_triage.csv` plus aggregate counts in `results/audit_triage_summary.csv`. Per-row evidence and reasons remain local. The second pass uses the same model family and is **not an independent human adjudication**. A verified quotation only confirms text presence, not a correct clinical interpretation. All rows retain human-review-pending status.

Review evidence candidates and domain-uncertain rows first, but do not automatically accept the other categories. Validate changes with synthetic regression tests; preserve the original sample and review history. `summarize_audit.py` reads only human answers, not model suggestions. Its agreement column is `yes / (yes + no + unsure)`; unsure and pending counts are reported separately, and this is not sensitivity, specificity or clinical accuracy.

Current local preliminary run: all 41 priority flags were triaged. The second pass matched the extractor on 4 rows, had quotation-support failures on 4, had no verified supporting quotation on 3, identified 26 evidence candidates for human review, and marked 4 as domain-uncertain. Human review of those 41 flags (Validation status above) confirmed none as extraction misses; no clinical mapping was changed.

## How to check it on the real data (locally only)

Run the derivation over the cases (strict mode) and look at **counts only**, such as "complicated appendicitis: 41 of 100". Do not paste patient text into chat tools or commit the per-case table. The synthetic tests in `tests/test_case_facts.py` use public ICD title wording only.
