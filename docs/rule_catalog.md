# Rule catalog (DRAFT, pending team review)

Code: `src/clinverify/rules/catalog.py`. Owner: Sneha. Status of every rule below: **DRAFT, not clinically validated**.

**Provenance.** This first set was drafted with an AI coding assistant, working only from one source the team has read (Hager et al., 2024, Fig. 4 and Methods). A rule becomes the team's rule only after the review steps at the bottom. The generating LLM never writes or sees the rules, so a plan is not graded against constraints it invented.

## What the first rules say

Hager et al. classify, for each of the four benchmark pathologies, the treatments that are **essential** (given to every patient of that pathology) as opposed to **case specific** (Methods, "Treatment requested"; counts in Fig. 4). Each rule requires one essential treatment when the plan's diagnosis is that pathology. Plans with another diagnosis satisfy the rule.

| Rule | If the plan's diagnosis is | the plan must recommend | Source |
|---|---|---|---|
| `R-TRT-001` | appendicitis | antibiotics | Hager 2024 Fig. 4; WSES 2020 appendicitis guidelines (Di Saverio et al., World J Emerg Surg 15:27) |
| `R-TRT-002` | appendicitis | supportive care | same |
| `R-TRT-003` | cholecystitis | antibiotics | Hager 2024 Fig. 4; WSES 2020 acute calculus cholecystitis guidelines (Pisano et al., World J Emerg Surg 15:61) |
| `R-TRT-004` | cholecystitis | supportive care | same |
| `R-TRT-005` | diverticulitis | antibiotics | Hager 2024 Fig. 4; ASCRS 2020 left-sided diverticulitis guidelines (Hall et al., Dis Colon Rectum 63:728-747) |
| `R-TRT-006` | diverticulitis | supportive care | same |
| `R-FUP-001` | diverticulitis | future colonoscopy | same; Hager: models "undertreat diverticulitis with the need for a colonoscopy in the future to check for colon cancer" |
| `R-TRT-007` | pancreatitis | supportive care | Hager 2024 Fig. 4; WSES 2019 severe acute pancreatitis guidelines (Leppaniemi et al., World J Emerg Surg 14:27) |

A plan must state its diagnosis (otherwise all rules are inconclusive). An empty treatment list means the plan recommends nothing and violates every rule for its diagnosis. Treatments are canonical concepts (`TREATMENT_CONCEPTS` in `plan.py`); mapping free text to them is the plan parser's job and a source of translation-fidelity error.

## Not encoded yet, and why

| Candidate | Reason it is not a rule yet |
|---|---|
| Case-specific treatments (appendectomy, cholecystectomy, colectomy, drainage, ERCP) | they depend on severity (for example a perforated colon for colectomy, infected necrosis for drainage), which a plan does not carry; needs conditions from the case record |
| Discharge only after ordered labs have resulted (the abstract's example) | needs a clinical source and a definition of "required" labs |
| No contraindicated medication (the abstract's example) | needs medication and allergy data (MIMIC-IV `prescriptions`, `pharmacy`) and a drug-interaction source |

## Review steps before a rule is final (see `docs/rule_authoring.md`)

- [ ] Someone reads the cited guideline itself, not only Hager's summary, and confirms the rule matches it (the first set rests on Hager's classification of essential treatments)
- [ ] A second team member reviews each rule and its source
- [ ] A clinician or domain reviewer, if available, checks the set (no clinician has been consulted so far)
- [ ] Rule IDs, wording and sources are copied into the report

## Tests

`tests/test_catalog.py` checks, for each rule, one compliant plan and one violating plan, the empty-treatment and missing-diagnosis cases, and scores 20 labeled synthetic plans (`tests/data/catalog_labeled_plans.json`) with the harness. Run: `python scripts/run_eval.py --plans tests/data/catalog_labeled_plans.json --rules clinverify.rules.catalog`.
