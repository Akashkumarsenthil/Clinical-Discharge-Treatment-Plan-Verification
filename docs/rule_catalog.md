# Rule catalog v1.0

Code: `src/clinverify/rules/catalog.py` (the single source of truth; this page is generated from it by
`scripts/build_rule_catalog_doc.py` and a test fails if the two differ). Owner: Sneha.

**Status: version 1.0 for team sign-off.** Each rule below was written from a numbered statement or section of a published
guideline whose full text was read, and is covered by tests. It is **not clinically validated**: no clinician has reviewed it.

**Provenance.** The first draft was prepared with an AI coding assistant. A rule becomes the team's rule through the sign-off in `docs/rule_signoff.md`.
The model that generates plans never writes or sees the rules, so a plan is not graded against constraints it invented.

## What the rules check

The rules check an LLM-generated plan for appendicitis, cholecystitis, diverticulitis and pancreatitis against guideline
recommendations that can be tested from a structured plan plus facts from the patient record:

- **Plan content** comes from the model: diagnosis, treatments (canonical concepts), antibiotic course in days, hours to appendectomy.
- **Case facts** come from the record, never from the model: for example whether the disease is complicated, or whether the patient is suitable for surgery (`CASE_FACTS` in `plan.py`).
- A rule **applies** only under its condition. If an applicable rule needs a plan field or case fact that is missing, the result is **insufficient information**, and the plan does not pass.
- A violated rule returns its **violation message**, which is also the feedback for the repair loop (Model C).

## The rules

| ID | Name | Applies when | Needs | Source and location | Strength as stated by the source |
|---|---|---|---|---|---|
| `R-GEN-001` | Diagnosis is in scope | always | `diagnosis` | Project scope: the four pathologies of MIMIC-IV-Ext-CDM (Hager et al. 2024, Nature Medicine 30:2613-2622) | scope guard |
| `R-APP-001` | Preoperative antibiotic dose before appendectomy | diagnosis is appendicitis and an appendectomy is planned | none | WSES 2020 acute appendicitis guideline (Di Saverio et al., World J Emerg Surg 15:27), Recommendation 7.1 | recommended (Recommendation 7.1; grade not shown beside this sentence) |
| `R-APP-002` | No postoperative antibiotics when uncomplicated | diagnosis is appendicitis and an appendectomy is planned | `facts.complicated`, `postop_antibiotic_days` | WSES 2020 acute appendicitis guideline (Di Saverio et al., World J Emerg Surg 15:27), Recommendation 7.1 (second sentence) | strong, high-quality evidence (1A) |
| `R-APP-003` | Postoperative antibiotics not longer than 5 days (complicated) | diagnosis is appendicitis | `facts.complicated`, `facts.source_control_adequate`, `postop_antibiotic_days` | WSES 2020 acute appendicitis guideline (Di Saverio et al., World J Emerg Surg 15:27), Recommendation 7.2 | strong, high-quality evidence (1A) |
| `R-APP-004` | Appendectomy within 24 hours (adults) | diagnosis is appendicitis and an appendectomy is planned | `facts.adult`, `appendectomy_hour` | WSES 2020 acute appendicitis guideline (Di Saverio et al., World J Emerg Surg 15:27), Recommendation 3.2 | strong, moderate-quality evidence (1B) |
| `R-CHO-001` | No routine postoperative antibiotics when uncomplicated | diagnosis is cholecystitis and a cholecystectomy is planned | `facts.complicated`, `facts.source_control_adequate`, `postop_antibiotic_days` | WSES 2020 acute calculus cholecystitis guideline (Pisano et al., World J Emerg Surg 15:61), Recommendation 7.1 | strong, high-quality evidence |
| `R-CHO-002` | Cholecystectomy first-line; drainage if unsuitable for surgery | diagnosis is cholecystitis | `facts.suitable_for_surgery` | WSES 2020 acute calculus cholecystitis guideline (Pisano et al., World J Emerg Surg 15:61), Recommendations 3.1 and 6.4 | strong; high-quality (3.1) and moderate-quality (6.4) evidence |
| `R-PAN-001` | No routine prophylactic antibiotics | diagnosis is pancreatitis and antibiotics are planned | `facts.infected` | WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27), antimicrobial therapy section | strong evidence grade (1A) |
| `R-PAN-002` | Antibiotics for infected severe pancreatitis | diagnosis is pancreatitis | `facts.infected`, `facts.severe` | WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27), antimicrobial therapy section | stated as always recommended (grade not separately shown) |
| `R-PAN-003` | Index-admission cholecystectomy (mild gallstone pancreatitis) | diagnosis is pancreatitis | `facts.gallstone`, `facts.mild` | WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27), section on timing of cholecystectomy | strong evidence grade (1A) |
| `R-PAN-004` | No routine ERCP in gallstone pancreatitis | diagnosis is pancreatitis and ERCP is planned | `facts.gallstone`, `facts.cholangitis`, `facts.cbd_obstruction` | WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27), ERCP section | strong evidence grade (1A) for 'not routine'; 1B and 2B for the exceptions |
| `R-PAN-005` | Enteral nutrition in severe pancreatitis | diagnosis is pancreatitis | `facts.severe` | WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27), nutrition section | recommended (grade not separately shown for this sentence) |
| `R-DIV-001` | No antibiotics for uncomplicated diverticulitis | diagnosis is diverticulitis and antibiotics are planned | `facts.immunocompetent`, `facts.complicated`, `facts.systemic_inflammation` | WSES 2020 acute colonic diverticulitis update (Sartelli et al., World J Emerg Surg 15:32), antibiotic therapy statements | strong, high-quality evidence (1A) |
| `R-DIV-002` | Postoperative antibiotics about 4 days (complicated) | diagnosis is diverticulitis and a postoperative antibiotic course is stated | `facts.complicated`, `facts.source_control_adequate`, `postop_antibiotic_days` | WSES 2020 acute colonic diverticulitis update (Sartelli et al., World J Emerg Surg 15:32), postoperative antibiotic statement | weak suggestion, moderate-quality evidence (2B): treat a violation as advisory |

Details per rule (recommendation paraphrase, violation message, valid and invalid synthetic example) are in the code.

## Sources (open-access full texts)

| Short name | Reference |
|---|---|
| APP | Di Saverio S. et al. (2020). Diagnosis and treatment of acute appendicitis: 2020 update of the WSES Jerusalem guidelines. World J Emerg Surg 15:27. https://doi.org/10.1186/s13017-020-00306-3 |
| CHO | Pisano M. et al. (2020). 2020 World Society of Emergency Surgery updated guidelines for the diagnosis and treatment of acute calculus cholecystitis. World J Emerg Surg 15:61. https://doi.org/10.1186/s13017-020-00336-x |
| PAN | Leppaniemi A. et al. (2019). 2019 WSES guidelines for the management of severe acute pancreatitis. World J Emerg Surg 14:27. https://doi.org/10.1186/s13017-019-0247-0 |
| DIV | Sartelli M. et al. (2020). 2020 update of the WSES guidelines for the management of acute colonic diverticulitis in the emergency setting. World J Emerg Surg 15:32. https://doi.org/10.1186/s13017-020-00313-4 |

## Why the first draft was replaced

The first draft (8 rules) was derived from Hager et al. (2024), who classify antibiotics, supportive care and a future colonoscopy as "essential"
treatments. Reading the guidelines themselves showed that this conflicts with them for uncomplicated cases:

| Hager-derived draft rule | What the guideline says |
|---|---|
| appendicitis and cholecystitis plans must contain antibiotics | recommends *against* postoperative antibiotics when uncomplicated (APP 7.1, CHO 7.1); only a single preoperative dose is recommended for appendectomy |
| diverticulitis plans must contain antibiotics | recommends *not* prescribing antibiotics for uncomplicated diverticulitis in immunocompetent patients without systemic inflammation (1A) |
| diverticulitis plans must schedule a colonoscopy | states that routine colonoscopy after uncomplicated diverticulitis may not be necessary; the ASCRS guideline that Hager cites was not read |

The draft rules were removed. This disagreement between a benchmark paper and the guidelines is worth reporting in section 4.

## Not covered, and why

| Candidate | Reason |
|---|---|
| Colonoscopy after diverticulitis | the WSES update does not require it routinely; ASCRS 2020 (paywalled) was not read |
| Severity-dependent surgery (colectomy for perforation, necrosectomy, interval appendectomy) | needs severity details the plan and record facts do not yet carry |
| Discharge before required labs resulted; contraindicated medication (the abstract's examples) | need a clinical source and medication data (MIMIC-IV `prescriptions`, `pharmacy`) |
| Children, pregnancy, special populations | guidelines give separate, mostly weaker statements; only adult appendectomy timing is encoded |

## Limits the team should state in the report

- Guidelines date from 2019-2020; newer versions may differ.
- Mapping free-text plans to the canonical treatment concepts is the plan parser's job, and a mapping error there is a translation-fidelity error.
- Two rules rest on weaker or less clearly graded statements and are marked so (R-DIV-002 weak suggestion; R-PAN-005 grade not separately shown). Treat their violations as advisory.
- No clinician has reviewed the set.

## Sign-off

Sign-off is recorded in **[docs/rule_signoff.md](rule_signoff.md)** (a separate page that people edit by hand; this page is generated and must not be edited).
Tick a rule only after reading its cited statement in the guideline itself; if you cannot tick it, write the reason in the Notes column.

## Run and test

```bash
python -m pytest tests/test_catalog.py
python scripts/make_catalog_labeled_plans.py        # regenerates the labeled synthetic plans (a test checks they are current)
python scripts/run_eval.py --plans tests/data/catalog_labeled_plans.json --rules clinverify.rules.catalog
python scripts/build_rule_catalog_doc.py            # regenerates this page
```
