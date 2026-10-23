# Model A plan format (output contract for the verifier)

Model A writes one plan per case. The verifier reads exactly the fields below. Anything else is rejected, so a plan can never be graded against facts the model made up.
Owner: Sneha (verifier side). Model A side: Ritika. Linear: T6-110 (output contract), T6-28 (connect Model A to the verifier).

## Output: a JSON list, one object per case

```json
[
  {
    "case_id": 20000123,
    "diagnosis": "appendicitis",
    "treatments": ["appendectomy", "preoperative_antibiotic"],
    "postop_antibiotic_days": 0
  }
]
```

| Field | Type | Meaning |
|---|---|---|
| `case_id` | int | the `hadm_id` of the benchmark case |
| `diagnosis` | one of `appendicitis`, `pancreatitis`, `diverticulitis`, `cholecystitis` | the model's diagnosis. `cholecystitis` has no rules yet, so those plans come back "diagnosis not covered" (R-GEN-001) |
| `treatments` | list of canonical concepts (below) | what the plan orders. Free text must be mapped to these concepts by the model's parser |
| `postop_antibiotic_days` | int >= 0, or `null` | days of antibiotics after surgery. `0` means none. Use `null` only if the plan says nothing (the rule is then "insufficient information") |

**Do not output case facts** (complicated, infection, biliary, and so on). They come from the patient record (`src/clinverify/data/case_facts.py`). A plan that includes a `facts` field is rejected.

## Treatment concepts

| Concept | Use it when the plan contains |
|---|---|
| `antibiotics` | any antibiotic treatment (not a single surgical prophylaxis dose) |
| `preoperative_antibiotic` | a single antibiotic dose before surgery as prophylaxis |
| `appendectomy` | surgical removal of the appendix |
| `cholecystectomy_during_admission` | gallbladder removal before discharge |
| `ercp` | endoscopic retrograde cholangiopancreatography |
| `parenteral_nutrition` | intravenous nutrition |
| `colonoscopy_after_recovery` | a colonoscopy planned after the acute illness |

Any other concept is rejected as unparseable. Mapping errors are counted as translation-fidelity errors.

## What the verifier returns per plan

- `valid`: no rule is violated and none is inconclusive.
- `violated`: names every broken rule ID (advisory rules are labelled "(advisory)").
- `insufficient_information`: a rule applies but a field or case fact is missing. These cases never count as valid.

Rules that need facts the record cannot give (`oral_or_enteral_feasible`, `low_risk`, `crc_screening_up_to_date`) stay "insufficient information" on real cases (see `docs/case_facts_mapping.md`).

## Run it

```bash
python scripts/verify_model_plans.py --plans model_a_plans.json
```

Reads the case facts from the data on your own machine (`MIMIC_DIR`). Prints counts only: statuses, violations by rule, unparseable plans, wrong diagnoses, and the validity rate. Per-case results (case IDs and rule IDs, no text) go to `results/model_runs/` (not committed).

Never send MIMIC text to a hosted LLM. Model A must run locally on the case text.
