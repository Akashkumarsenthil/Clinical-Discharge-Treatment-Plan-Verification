# Where the system loses (Template §6.5)

**Status:** draft from frozen validation aggregates only (seed 298). No test-split claims. No new model runs.  
**Companion figure:** [`images/baseline_vs_model_a.png`](images/baseline_vs_model_a.png) · [`baseline_vs_model_a.md`](baseline_vs_model_a.md)  
**Sources:** [`validation_summary.json`](validation_summary.json), [`evaluation_feasibility.md`](evaluation_feasibility.md), [`baseline_notes.md`](baseline_notes.md).

The course template requires an explicit account of where the approach is **worse** than a baseline or alternative, quantified. This page is that account for Model A (prompted Qwen2.5:14b + Z3 catalog v2.1) on the **validation** split (460 cases).

## 1. Loses to Model E on plan metrics (same split)

Model E is a TF-IDF + logistic regression reference on the same validation cases. It is **not** one of the four topic models. On diagnosis the two methods tie; on plan checks Model A is worse.

| Metric | Model E | Model A | Gap (A − E) |
|---|---:|---:|---:|
| Diagnosis accuracy (460) | 88.7% | 88.7% | 0.0 |
| Macro F1 (diagnosis) | 0.853 | 0.855 | ≈0 |
| Checked acceptance (336 covered) | **18.8%** (63/336) | **14.6%** (49/336) | **−4.2 pp** |
| Joint success (460) | **16.3%** | **12.0%** | **−4.3 pp** |

**Interpretation.** A large prompted LLM does not beat a cheap text classifier at naming the pathology here, and it produces fewer verifier-accepted plans with a decided clinical check. The project’s value is the **checker**, not a claim that Model A is the best diagnostic model.

## 2. Loses most often to “cannot decide,” not to a named rule break

Of 460 Model A plans:

| Status | Count | Share of 460 |
|---|---:|---:|
| Valid | 57 | 12.4% |
| Violated | 123 | 26.7% |
| Insufficient information | **280** | **60.9%** |

So the dominant loss mode is **insufficient information**: a blocking rule applies but a plan field or record-derived case fact is missing/unknown. That is non-acceptance under protocol v1.1; it is not proof the clinical case is untreatable or that the model invented a contraindicated treatment.

Among recorded rule hits on this run:

| Rule | Count | Meaning (short) |
|---|---:|---|
| R-GEN-001 | **106** | Diagnosis not in the treatment catalog (mostly cholecystitis scope) |
| R-APP-003 | 46 | Post-op antibiotic duration bound (appendectomy / complicated path) |
| R-DIV-002 | 14 | Colonoscopy after complicated diverticulitis |
| R-APP-002 | 2 | No post-op antibiotics when uncomplicated |
| R-PAN-002 | 1 | Empiric antibiotics for infected necrosis |

**Do not read “123 violated” as 123 clinical disasters.** More than four-fifths of the listed violation hits are the **scope guard** (R-GEN-001). Report cholecystitis as unsupported for treatment metrics, not as Model A “failing care.”

## 3. Loses to the record / catalog ceiling (software bound)

Even with a perfect diagnosis and an optimistically chosen schema plan, strict facts limit automatic acceptance ([`evaluation_feasibility.md`](evaluation_feasibility.md)). On the **test** covered set the checked-acceptance ceiling is only **18/73 (24.7%)**; all **22** test pancreatitis cases have an unavoidable unknown on at least one of R-PAN-002 / R-PAN-003. Validation shows the same pattern at scale: many plans cannot earn checked acceptance because facts the rules need are not derivable.

So Model A also “loses” to **coverage of case facts and rules**, not only to generation quality. Raising automatic acceptance by hiding unknowns would violate the frozen protocol.

## 4. What we do *not* claim as a loss to Hager

Published Hager OASST 70B mean diagnostic accuracy is **54.9%** (autonomous, 2,400 cases). Our reduced baseline is **47.4%** (Llama 3.1 8B, 400 cases). Model A diagnosis on **our** validation split is **88.7%**.

These are **different tasks and cohorts**. We do **not** say Model A beats Hager, and we do **not** say it loses to Hager on plan validity — Hager’s headline number is diagnosis-only and has no Z3 plan metric.

## 5. Conditions under which this system should not be used

- As a **clinical decision** product or as proof a plan is medically correct (“valid” = catalog compliance only).
- On pathologies **outside** catalog v2.1 treatment rules (cholecystitis today): expect R-GEN-001 / unsupported treatment scoring.
- When case facts needed by blocking rules are **unknown**: expect insufficient information, not a green light.
- For automatic **0.85** treatment validity: infeasible under strict facts; 0.85 remains a human-adjudication research goal only.

## 6. What would reduce these losses (later work, not claimed done)

| Loss mode | Direction |
|---|---|
| Below Model E on checked acceptance | Better plans and/or repair loop (Model C, 298B); optional FT/RAG ablations when run |
| Insufficient information | Richer derivable facts, or human adjudication endpoint — not silencing unknowns |
| R-GEN-001 volume | Extend catalog for cholecystitis, or keep reporting scope separately |
| Catalog ceiling | Honest reporting; do not retarget the metric after seeing scores |

## One-line summary for slides

**Model A ties a cheap classifier on diagnosis and loses on plan checked acceptance (−4.2 pp vs Model E); most non-acceptances are insufficient information (280/460) or catalog scope (R-GEN-001 = 106), not a single dominant clinical rule break.**
