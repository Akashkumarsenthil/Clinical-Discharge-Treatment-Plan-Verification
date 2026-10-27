# Evaluation feasibility check — October 23, 2026

This is a local inspection of strict record facts and catalog v2.1 software behaviour **before Model A experiments**, not model performance, clinical accuracy or recommended care. Both validation and test facts were inspected; disclose this when describing protocol v1.1. No patient text or case IDs are published here. Extraction has a 116-row mapping-consistency audit ([`case_facts_validation.csv`](case_facts_validation.csv)); that is not clinician sign-off.

## Reproduce locally

```bash
python scripts/check_evaluation_feasibility.py --cohort validation
# Aggregate inspection across validation, test and the entire benchmark:
python scripts/check_evaluation_feasibility.py --cohort all-groups
```

The script reads the local credentialed dataset, defaults to validation, prints aggregate JSON, and writes no files. It does not generate model outputs, prompts, labels or patient text. The full 2,400-case benchmark includes training and validation cases and is not a held-out performance population.

## Results

Both bounds assume perfect diagnosis and optimistically chosen schema outputs. Neither is a guarantee that a clinically adequate plan exists or will be generated.

| Population | Scheduled / covered | Legacy schema-acceptance bound | Checked-acceptance bound |
|---|---:|---:|---:|
| Validation | 460 / 336 | 229/336 = 68.2% | 76/336 = 22.6% |
| Test | 100 / 73 | 47/73 = 64.4% | 18/73 = 24.7% |
| Entire benchmark | 2,400 / 1,752 | 1,155/1,752 = 65.9% | 374/1,752 = 21.3% |

Test-pathology detail:

| Reference pathology | Cases | Legacy bound | Checked bound |
|---|---:|---:|---:|
| Appendicitis | 40 | 40 | 11 |
| Pancreatitis | 22 | 0 | 0 |
| Diverticulitis | 11 | 7 | 7 |

All 22 test pancreatitis cases have an unavoidable unknown on at least one of R-PAN-002/R-PAN-003. Each of those rules individually has 19 unknowns; the affected-case sets overlap, so their counts cannot be added. Four diverticulitis cases have an unavoidable unknown for R-DIV-002. Appendicitis has a different loophole: omitting surgery bypasses both postoperative checks, even when complication status is unknown. Of 40 appendicitis cases, only 11 permit a verifier-accepted plan with a decided blocking clinical check. These limitations are not proof that the underlying clinical cases are untreatable or that a model is wrong.

## Enumeration and interpretation

For each distinct pathology/fact profile the script enumerates every subset of the disease-relevant canonical treatment tokens: 4 choices for appendicitis, 16 for pancreatitis and 4 for diverticulitis. Other diseases' tokens do not affect that disease's v2.1 rules. Postoperative antibiotic days are set to zero for appendicitis: zero satisfies both encoded duration constraints whenever they can be checked; another or missing duration cannot improve existential acceptance. This is **not** a recommendation to prescribe zero days. The catalog explicitly does not encode every indication or completeness requirement.

The legacy bound counts a case if any enumerated, correctly diagnosed plan is accepted. The checked bound additionally requires at least one decided **non-advisory clinical** rule; the scope guard, unknown and not-applicable rules do not count. Plan choices may be incomplete or inappropriate: a schema upper bound is deliberately more optimistic than clinical success. The script refuses a catalog version other than v2.1; review the enumeration if clinical logic or fields change.

The previous 85% goal would require at least **63/73** automatic acceptances. Even the permissive legacy bound is only **47/73**. Replacing test cases with the full benchmark would not solve missing evidence, and including the 27 unsupported test pathologies as treatment failures would also confound scope with correctness.

## Protocol consequence

Protocol v1.1 keeps the split, all 73 covered cases, strict facts, clinical catalog and verifier verdicts unchanged. Automatic acceptance metrics are **descriptive**, with unknowns and coverage reported separately. Checked acceptance prevents scope-only or advisory-only acceptance from being presented as primary automatic success, but still does not establish clinical completeness.

The 85% value is retained only as an **unverified independent-adjudication research goal**, not a lowered or selectively filtered automatic score. Record evaluability must be human-assessed for all covered cases, blind to model outputs and verifier outcomes, and frozen before generation. Later human plan review must assess adequacy/completeness and validity independently. Its eligible denominator, exclusions and uncertainty must be reported. The label scorer exists ([adjudication_labels.md](adjudication_labels.md)); no eligibility manifest or generated-plan labels exist yet, so the automatic runner returns that endpoint as unavailable. The current fact audit is not a substitute.

See [metrics.md](metrics.md), [protocol v1.1](evaluation_protocol.json) and the unchanged [v1.0 archive](evaluation_protocol_v1.0.json). This check changes no rule approval, human review answer or clinical validation claim.
