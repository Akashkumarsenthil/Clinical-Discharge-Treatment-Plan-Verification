# Rule catalog v2.0

Code: `src/clinverify/rules/catalog.py` (the single source of truth; this page is generated from it by
`scripts/build_rule_catalog_doc.py` and a test fails if the two differ).

**Status: version 2.0 for team sign-off.** Each rule below was written from a statement in a guideline or systematic review published in 2025-2026
(the course asks for sources no older than 3-4 years), and is covered by tests. The source column says whether the full text or only the abstract was read. It is **not clinically validated**: no clinician has reviewed it.

**Provenance.** The first draft was prepared with an AI coding assistant. A rule becomes the team's rule through the sign-off in `docs/rule_signoff.md`.
The model that generates plans never writes or sees the rules, so a plan is not graded against constraints it invented.

## What the rules check

The rules check an LLM-generated plan for appendicitis, pancreatitis and diverticulitis against guideline
recommendations that can be tested from a structured plan plus facts from the patient record:

- **Plan content** comes from the model: diagnosis, treatments (canonical concepts), antibiotic course in days.
- **Case facts** come from the record, never from the model: for example whether the disease is complicated, or whether the patient is suitable for surgery (`CASE_FACTS` in `plan.py`).
- A rule **applies** only under its condition. If an applicable rule needs a plan field or case fact that is missing, the result is **insufficient information**, and the plan does not pass.
- A violated rule returns its **violation message**, which is also the feedback for the repair loop (Model C).

## The rules

| ID | Name | Applies when | Needs | Source and location | Strength as stated by the source |
|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is covered by the rules | always | `diagnosis` | Project scope: the rule set covers appendicitis, pancreatitis and diverticulitis (benchmark pathologies of Hager et al. 2024) | scope guard |
| `R-APP-001` | Antibiotic prophylaxis for appendectomy | diagnosis is appendicitis and an appendectomy is planned | none | Swedish national guidelines for acute appendicitis (Salo et al., BJS Open 2025;9:zrae165; full text), antibiotic recommendations for appendectomy | GRADE high certainty of evidence (four-plus rating) |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | diagnosis is appendicitis and an appendectomy is planned | `facts.complicated`, `postop_antibiotic_days` | Swedish national guidelines for acute appendicitis (Salo et al., BJS Open 2025;9:zrae165; full text), antibiotic recommendations for appendectomy | GRADE high certainty of evidence (four-plus rating) |
| `R-APP-003` | Short postoperative antibiotic course (complicated) | diagnosis is appendicitis | `facts.complicated`, `postop_antibiotic_days` | 2025 WSES Jerusalem guidelines for acute appendicitis (Podda et al., JAMA Surg 2026;161:283-295; abstract only), key findings in the abstract | stated in the abstract of the 2025 edition; grade not shown there |
| `R-PAN-001` | No prophylactic antibiotics | diagnosis is pancreatitis and antibiotics are planned | `facts.infection` | Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text), antibiotic recommendations | strong recommendation, high-quality evidence |
| `R-PAN-002` | Empiric antibiotics for infected necrotizing pancreatitis | diagnosis is pancreatitis | `facts.necrotizing`, `facts.infection` | Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text), explanatory text of the antibiotic recommendations | stated in the explanatory text; no strength label shown beside this sentence |
| `R-PAN-003` | Cholecystectomy during the index admission (mild biliary pancreatitis) | diagnosis is pancreatitis | `facts.biliary`, `facts.mild` | Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text), cholecystectomy recommendations | strong recommendation, high-quality evidence |
| `R-PAN-004` | ERCP only for cholangitis or biliary obstruction | diagnosis is pancreatitis and ERCP is planned | `facts.biliary`, `facts.cholangitis`, `facts.biliary_obstruction` | Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text), ERCP recommendations and explanatory text | strong, high-quality evidence for urgent ERCP with cholangitis; weak, moderate-quality evidence for delaying it without cholangitis. The 'discouraged' wording is advisory. |
| `R-PAN-005` | Parenteral nutrition only as a last resort | diagnosis is pancreatitis and parenteral nutrition is planned | `facts.oral_or_enteral_feasible` | Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text), nutrition recommendations | strong recommendation, high-quality evidence |
| `R-DIV-001` | No routine antibiotics when uncomplicated and low risk | diagnosis is diverticulitis and antibiotics are planned | `facts.complicated`, `facts.low_risk` | ACG clinical guideline on colonic diverticulitis (Peery et al., Am J Gastroenterol 2026;121:1549-1561; abstract only), recommendation on antibiotics; Korean guidelines for acute colonic diverticulitis (Lee et al., Intest Res 2026;24:428-463; full text), antibiotic recommendation for uncomplicated diverticulitis | ACG: suggestion; KASID: conditional recommendation, high-quality evidence. Advisory. |
| `R-DIV-002` | Colonoscopy after complicated diverticulitis | diagnosis is diverticulitis | `facts.complicated` | ACG clinical guideline on colonic diverticulitis (Peery et al., Am J Gastroenterol 2026;121:1549-1561; abstract only), recommendation on colonoscopy after diverticulitis | recommended (wording of the abstract; strength label not read) |
| `R-DIV-003` | Colonoscopy suggested after uncomplicated diverticulitis in selected patients | diagnosis is diverticulitis | `facts.complicated`, `facts.alarm_symptoms`, `facts.crc_screening_up_to_date` | ACG clinical guideline on colonic diverticulitis (Peery et al., Am J Gastroenterol 2026;121:1549-1561; abstract only), recommendation on colonoscopy after diverticulitis | suggested (wording of the abstract; strength label not read). Advisory. |

Details per rule (recommendation paraphrase, violation message, valid and invalid synthetic example) are in the code.

## Sources (all 2025-2026)

| Short name | Reference | Read |
|---|---|---|
| SWE | Salö M. et al. (2025). Antibiotic prophylaxis and postoperative antibiotics in appendicitis: systematic review and guideline. BJS Open 9:zrae165 | full text |
| WSES25 | Podda M. et al. (2026). Acute appendicitis guideline update (WSES). JAMA Surg 161:283-295 | abstract only |
| ILATAM | Cárdenas-Jaén K. et al. (2026). Acute pancreatitis guideline (iLATAM). United European Gastroenterol J 14:e70190 | full text |
| ACG26 | Peery A.F. et al. (2026). ACG clinical guideline: diverticulitis. Am J Gastroenterol 121:1549-1561 | abstract only |
| KASID26 | Lee K.-M. et al. (2026). KASID guideline on diverticular disease. Intest Res 24:428-463 | full text |

Rules that rest on an abstract are weaker: read the full text before ticking them.

## Why version 1.0 was replaced

Version 1.0 (14 rules) used WSES guidelines from 2019-2020. The course asks for sources no older than 3-4 years, so version 2.0 uses only 2025-2026 sources.
Rules whose newer source could not be read were not carried over:

| Dropped from v1.0 | Reason |
|---|---|
| Cholecystitis rules (R-CHO-001, R-CHO-002), `cholecystitis` as a covered diagnosis | no recent guideline with readable full text; cholecystitis plans now return R-GEN-001 |
| Appendectomy within 24 hours (R-APP-004) | no readable recent source for the timing threshold |
| Old R-DIV-002 (about 4 days of postoperative antibiotics) | replaced by the ACG 2026 / KASID 2026 rules R-DIV-001 to R-DIV-003 |

## Not covered, and why

| Candidate | Reason |
|---|---|
| Newest full-text guidelines (IAP 2025, WSES 2025 full text, ACG 2026 full text, ASCRS 2026, ACP 2022) | paywalled; not read |
| Severity-dependent surgery (colectomy for perforation, necrosectomy, interval appendectomy) | needs severity details the plan and record facts do not yet carry |
| Discharge before required labs resulted; contraindicated medication (the abstract's examples) | need a clinical source and medication data (MIMIC-IV `prescriptions`, `pharmacy`) |
| Children, pregnancy, special populations | separate, mostly weaker statements |

## Limits the team should state in the report

- Sources date from 2025-2026; two were read as abstracts only.
- Mapping free-text plans to the canonical treatment concepts is the plan parser's job, and a mapping error there is a translation-fidelity error.
- Rules marked advisory (R-APP-003, R-PAN-004, R-DIV-001, R-DIV-003) rest on weaker or conditional statements; their violations print '(advisory)' and are not blocking.
- No clinician has reviewed the set.

## Sign-off

Sign-off is recorded in **[docs/rule_signoff.md](rule_signoff.md)** (a separate page that people edit by hand; this page is generated and must not be edited).
Tick a rule only after reading its cited statement in the source itself; if you cannot tick it, write the reason in the Notes column.

## Run and test

```bash
python -m pytest tests/test_catalog.py
python scripts/make_catalog_labeled_plans.py        # regenerates the labeled synthetic plans (a test checks they are current)
python scripts/run_eval.py --plans tests/data/catalog_labeled_plans.json --rules clinverify.rules.catalog
python scripts/build_rule_catalog_doc.py            # regenerates this page
```
