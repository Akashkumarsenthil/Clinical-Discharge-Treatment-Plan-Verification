# Evaluation metrics v1.1

**Definitions frozen locally: October 23, 2026.** Machine-readable record: [evaluation_protocol.json](evaluation_protocol.json). This freezes definitions for future Model A validation/test runs, not human rule approval or clinical validation. The second human rule review remains pending. The manual fact audit is deferred at the user's request and its human-answer columns remain blank.

Existing synthetic tests, pipeline checks and preliminary audit outputs predate this freeze. Do not call it preregistration before all results existed. Those engineering checks establish no Model A held-out performance claim. Commit this record before formal held-out runs; a `metrics-frozen` Git tag has **not** been created automatically.

## Revision and feasibility

On October 23, before Model A experiments, a local inspection of strict record facts showed that the 85% automatic acceptance target is infeasible. Even with perfect diagnosis and optimistically chosen schema outputs, the test ceiling is 47/73 (64.4%); the analogous validation ceiling is 229/336 (68.2%). These are software bounds, not clinically valid plans or observed model performance. The enumeration can choose incomplete or inappropriate treatments, so actual clinically meaningful acceptance can be lower. See [evaluation_feasibility.md](evaluation_feasibility.md).

**v1.1 removes the 0.85 target from automatic full-cohort acceptance.** It adds a stricter, descriptive checked-acceptance metric to prevent scope-only/advisory-only acceptance from earning primary automatic credit. The 0.85 value is retained only as an **unverified research goal for independent human-adjudicated treatment validity** on a record-evaluable cohort; that endpoint is unavailable today. It is a different estimand, not a claim that the original target was achieved or is now achievable. The old [v1.0 protocol](evaluation_protocol_v1.0.json) is archived unchanged (also Git revision `ebe3d4b`). Split, strict facts, clinical rules and verifier verdicts are unchanged. Both validation and held-out test facts were inspected for this feasibility decision; disclose this and do not call the revised protocol untouched by test-data inspection. No Model A held-out performance was inspected.

The target concern previously tracked as **Linear T6-160** is addressed locally by this revision; this does not change the external task's status or certify team approval. The new checked-acceptance ceiling is **18/73 (24.7%)**, versus **47/73 (64.4%)** for the legacy acceptance diagnostic. Earlier 11-case/18-case illustrative plan counts were not universal bounds and must not be reported as such. No numerical target is applied to either automatic rate.

## Population and repeat runs

- Use split v2, grouped by patient: 1,840 training, 460 validation, **100 test encounters**. Its SHA-256 is pinned in the protocol. Never tune prompts/rules against held-out model results.
- **User-selected treatment population:** the original test split contains 73 appendicitis/pancreatitis/diverticulitis cases and 27 cholecystitis cases. Diagnosis is scored on all 100; automatic treatment metrics retain all 73 covered cases, **without a numerical acceptance target**. The other 27 are unsupported for treatment evaluation, not clinical treatment failures. The 73-case membership hash is pinned too; this is a scope-based selection before Model A experiments, not selection by model performance. The validation split similarly has 336 covered and 124 unsupported cases. Do not evaluate on the whole 2,400-case benchmark and call it held-out performance: it contains training and validation cases.
- Start on validation cases. `pilot` scores submitted outputs only and is not an official test estimate.
- Request one plan per scheduled case per run. Missing generations stay in the denominator. Malformed treatment plans fail validity. Duplicate, out-of-cohort or unidentifiable case IDs reject the run; do not cherry-pick an output.
- Use generation seeds **298, 299 and 300** with the same frozen model, prompt and decoding settings. Report each run plus mean and standard deviation across seeds. Do not treat 300 generations as 300 independent patients. Choose and record decoding settings before the first formal test, not by test performance.
- Record exact model/digest, prompt SHA-256, seed, temperature, top-p, token limit, protocol version, source/split hashes, Git revision and dirty-state flag. A dirty tree is disclosed, not falsely represented as a tagged release.
- **Strict facts are the main analysis.** Label sensitivity results separately; the formal CLI uses strict extraction. Final ICD/discharge diagnoses are retrospective judging evidence, never model-generation input. Extraction remains unvalidated while human audit is pending, so real-data findings remain provisional even though definitions are frozen.

## Exact definitions

Let **N** be all scheduled cases (100 on test), **C** the covered scheduled cases (73), **D** those with a correct canonical diagnosis label, **V** fully parsed plans accepted by the verifier, **J** cases in both D and V, and **Jc** the covered cases in J. Diagnosis labels are scored independently of treatment parsing: a correct diagnosis with malformed treatment fields counts in D but not V or J.

| Output | Numerator / denominator | Meaning |
|---|---|---|
| `diagnosis_accuracy` | D / N | Missing/invalid diagnostic labels are not correct. |
| **`supported_checked_acceptance_rate`** | Correctly diagnosed, accepted covered plans with at least one decided non-advisory clinical rule / C | **Primary automatic treatment metric; descriptive, no numerical target.** Scope guard, advisory-only and not-applicable rules cannot earn credit. A passed prophylaxis check does not establish completeness of an entire plan. |
| `supported_treatment_validity_rate` | Jc / C | Legacy covered-cohort acceptance diagnostic, retained unchanged for compatibility; **no 0.85 target**. Can credit plans with no decided blocking clinical check. Missing, malformed, wrong-diagnosis and blocking-inconclusive covered cases remain non-acceptances, not necessarily proven clinical errors. |
| `adjudicated_treatment_validity_rate` | Independently adjudicated clinically adequate/valid, correctly diagnosed plans / fixed record-evaluable covered cohort E | Research goal >= 0.85; **unavailable until independent human eligibility and complete generated-plan labels exist and their scorer is implemented/tested**. Not computed from verifier acceptance. |
| `validity_rate` | V / N | Legacy all-submission rule-compliance diagnostic. No 0.85 target is applied to this rate under the user-approved scope decision. It can include wrong diagnoses and scope failures; never report it alone. |
| `validity_rate_diagnosis_correct` | J / D | Treatment-rule compliance among correct diagnoses, including malformed treatment outputs as failures. |
| `supported_treatment_validity_given_correct_diagnosis` | Jc / correctly diagnosed covered cases | Conditional treatment metric restricted to covered pathologies; report its denominator. |
| `supported_rule_compliance_rate` | Accepted plans on covered cases / C | Diagnostic only: unlike the primary metric, does not require diagnosis correctness. |
| `joint_success_rate` | J / N | Correct diagnosis and an accepted plan. Mandatory companion metric; no new numerical target invented. |
| Unparseable count | Submitted plans failing the schema/parser | Fail validity, not silently excluded. |
| Missing-output count | Scheduled cases without a submitted record | Fail validity and diagnosis accuracy. |
| `n_valid_without_clinical_checks` | Accepted plans with no decided clinical rule, excluding the scope guard | Mandatory coverage warning; not evidence of clinical safety. |

A zero denominator gives **null / unavailable**, never an apparent 0% or 100%. Report counts with rates. Record `n_supported_cases`, `n_unsupported_cases`, `treatment_status` (legacy verifier statuses), and `checked_treatment_status` beside the primary result. Each treatment-status table partitions covered cases only. The checked table distinguishes `accepted_with_decided_blocking_clinical_check` from `accepted_without_decided_blocking_clinical_check`; only the former earns primary automatic credit. Its numerator is `n_supported_checked_accepted`. Also report `n_supported_accepted_without_decided_blocking_clinical_check` and `n_empty_treatment_plans`. Empty plans are not automatically declared clinically wrong: this schema does not encode all supportive care, but an empty plan cannot earn checked acceptance from this catalog. Nonempty plans can also be incomplete. Legacy raw verifier diagnostics may flag R-GEN-001 on cholecystitis; report those as unsupported scope, not clinical treatment errors. A wrong diagnosis must never move an encounter into or out of the covered population: membership comes from the benchmark's reference pathology, not the model's answer. Show pathology-stratified results as well.

## Independent adjudication and the 85% research goal

Before Model A generation, qualified independent human reviewers must assess record sufficiency for **all 73 covered cases**, without viewing generated outputs, model identity or verifier verdicts. Freeze an eligibility manifest, its hash, reviewer/date, reasons and the evaluable count **E**. Eligibility must not be selected from passing outputs, known extraction facts or verifier-decided cases. Report **E/73**, excluded-case reasons and pathology mix alongside any conditional score. The original 73-case automatic denominator is never replaced by E.

After generation, independent reviewers evaluate clinical adequacy/completeness and validity, using the record rather than copying rule outcomes. The numerator requires correct diagnosis and an adequate/valid plan. Missing, malformed, wrong-diagnosis and clinically incomplete plans on eligible cases are failures, not exclusions. Unresolved labels prevent a final target claim; do not shrink E to completed favourable reviews. Resolve reviewer disagreements with a documented adjudication process. Ineligible cases stay visible in full-cohort automatic metrics. A conditional 85% result is not 85% success on all 73 cases and needs its count, coverage and uncertainty reported; feasibility is not established yet.

The current automatic runner deliberately returns `adjudicated_treatment_validity_rate: null` and an unavailable status. An independently labelled plan schema and tested scorer still need to be implemented before this endpoint can be claimed; no human labels are fabricated by this revision. The deferred 116-row fact audit and rule-catalog sign-off are separate tasks, not clinical labels for generated plans. If the team cannot arrange qualified independent plan review, report the automatic metrics descriptively and mark the 85% goal unassessed; do not invent a new automatic denominator to hit it.

## Unknown, not applicable and advisory findings

- A blocking violated rule yields `violated`. With none violated, a blocking missing input yields `insufficient_information`. Neither counts as valid.
- A known-false condition is **not applicable**, not a passed check. An unknown OR operand is unnecessary when a known positive already decides the condition.
- **Advisory violations and advisory unknowns do not block validity.** Report them separately in per-case findings, per-rule counts, `n_with_advisory_finding` and `n_with_advisory_unknown`. A valid plan can still be incompletely evaluated.
- For each rule report **not_applicable, unknown, passed, violated**, with its advisory flag. These four counts sum to fully parsed/verified plans, **not N** if outputs are missing or malformed. `per_rule_denominator` records this population.
- Report `per_rule_diagnosis_correct` and its denominator too. The all-plan table includes wrong-diagnosis submissions for diagnostic purposes; their disease-specific checks are not valid treatment evidence.
- `per_rule_supported_correct` is the primary treatment table: fully parsed, correctly diagnosed, covered cases. Its denominator is separately recorded. Unsupported, missing, malformed and wrong-diagnosis cases are not passed clinical checks; keep their top-level counts visible.
- Publish facts-only potential coverage beside actual applicability. A fact-testable case may not be checked because surgery/ERCP/antibiotic planning determines applicability. Acceptance-only examples cannot demonstrate detection of inappropriate treatment.

## Escape rate and labelled-verifier checks

The abstract's escape target **<= 0.05** is preserved. For a real-data claim it concerns independently labelled generated plans on the covered treatment population, not unsupported cholecystitis scope failures. It needs appropriate reference labels, not the verifier's own verdicts on unlabeled outputs.

| Metric | Exact numerator / denominator |
|---|---|
| Blocking escape rate | Reference-labelled blocking-invalid plans accepted as valid / all reference-labelled blocking-invalid plans. Inconclusive plans are not escapes. |
| False-reject rate | Reference-labelled blocking-valid plans not accepted as valid / all reference-labelled blocking-valid plans. A blocking unknown is non-acceptance and is separately reported. |
| Exact blocking-rule match | Blocking-invalid plans whose flagged blocking IDs equal reference blocking IDs / all reference-labelled blocking-invalid plans. |

Advisory-only reference violations do not make a plan blocking-invalid. Without labels, escape/false-reject rates are **unavailable**. Do not manufacture ground truth using the same catalog. The 29 catalog-generated synthetic plans test software consistency, not independent clinical accuracy. A real-data escape claim needs independent adjudication of held-out generated plans; the current fact audit is not such a plan-label dataset.

The labelled harness uses **1,000 bootstrap resamples, seed 298, percentile 95% intervals**, with denominators. Small synthetic samples can give degenerate intervals; these do not establish clinical safety. Real-data batch scoring currently reports point estimates, not patient-cluster confidence intervals.

## Solver cost and later-semester metrics

- Solver cost is descriptive: verifier milliseconds per fully parsed plan, mean and p95. It includes applicability/missing-input checks and solver work, not LLM generation or data loading. No latency target is invented.
- Repair success (Model C) and translation fidelity (Model B) are **298B** work. Freeze their detailed protocols before those experiments; missing future targets do not block the 298A definition freeze.
- Hager baseline diagnostic accuracy is not directly comparable with plan compliance. Compare like-for-like tasks/settings and disclose reproduction deviations.

## Running and approval state

```bash
# Validation run: all 460 scheduled validation cases stay in the denominator.
python scripts/verify_model_plans.py --plans model_a_plans.json --cohort validation

# Formal 100-case test: exact generation metadata is required.
python scripts/verify_model_plans.py --plans model_a_test_plans.json --cohort test --generation-metadata run_metadata.json
```

Metadata keys: `model`, `model_digest`, `prompt_sha256`, `seed`, `temperature`, `top_p`, `max_new_tokens`. Never include patient text. Settings must describe the generation that actually happened; the scorer records a declaration, not proof of an external model's execution.

| Item | Status |
|---|---|
| Metric definitions, denominators, unknown/advisory policy | Revised locally as protocol v1.1; v1.0 archived; no clinical rules or split changed |
| Targets and treatment population | Automatic treatment metrics descriptive on all 73 covered cases; 0.85 research goal only on independently adjudicated evaluable plans (unavailable); 0.05 escape on independently labelled covered plans; diagnosis accuracy on all 100 |
| Independent plan eligibility, adjudication and label scorer | Pending, not supplied by the fact audit or automatic verifier |
| First human rule reviewer | Existing entries preserved in `rule_signoff.md` |
| Second human rule reviewer | **Pending; cannot be completed by the assistant** |
| Manual case-fact audit | Deferred by user; human answers left blank |
| Exact Model A model/prompt/decoding settings | Record before formal test; Model A not implemented yet |
| Git commit and `metrics-frozen` tag | Not created by this edit |

Definition or clinical-rule changes after held-out results require a new version, dated rationale, preserved earlier results and a disclosed evaluation consequence. A changed held-out split cannot be scored under the old hash pin. This freeze does not certify clinical completeness of the catalog or extraction.
