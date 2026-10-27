# Independent plan eligibility and labels

This is the schema for the **0.85 research goal** and labelled escape / false-reject rates. It is separate from catalog acceptance and from the case-fact audit.

**Status (2026-10-27):** the label **scorer is implemented** (`src/clinverify/eval/adjudication.py`, wired through `verify_model_plans` and `scripts/verify_model_plans.py`). **No human eligibility manifest or plan labels exist yet**, so production runs still return `adjudicated_treatment_validity_rate: null`. Do not invent clinical labels.

## Order of work

1. **Before Model A generation:** a qualified reviewer fills an eligibility manifest for **all 73 covered test cases**, blind to plans, model identity and verifier outcomes. Freeze the file and record its SHA-256.
2. **After generation:** an independent reviewer labels every **eligible** plan (adequacy/completeness and validity from the record, not by copying the catalog).
3. **Score:** pass both files to the verifier CLI. Unresolved labels (`null`) block the research rate; they are not dropped.

## Eligibility manifest (`schema_version` 1)

```json
{
  "schema_version": 1,
  "catalog_version": "2.1",
  "reviewer": "INITIALS",
  "review_date": "YYYY-MM-DD",
  "blind_to_plans": true,
  "cases": [
    {"case_id": 20000123, "eligible": true, "reason": ""},
    {"case_id": 20000456, "eligible": false, "reason": "insufficient record for treatment judgement"}
  ]
}
```

- Every covered case ID must appear exactly once.
- Ineligible rows need a non-empty `reason`.
- `blind_to_plans` must be `true`.

## Plan labels (`schema_version` 1)

```json
{
  "schema_version": 1,
  "eligibility_manifest_sha256": "<hash of the frozen eligibility object>",
  "reviewer": "INITIALS",
  "review_date": "YYYY-MM-DD",
  "labels": [
    {
      "case_id": 20000123,
      "diagnosis_correct": true,
      "clinically_adequate_and_valid": true,
      "blocking_invalid": false,
      "blocking_rule_ids": [],
      "notes": ""
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `diagnosis_correct` | human judgement that the plan diagnosis matches the record |
| `clinically_adequate_and_valid` | adequate/complete and clinically valid treatment plan; `null` = unresolved |
| `blocking_invalid` | optional; used for labelled escape / false-reject vs the verifier |
| `blocking_rule_ids` | optional reference IDs; do not copy the verifier blindly |
| `notes` | short rationale; **no patient text** |

Success for the research rate: `diagnosis_correct` and `clinically_adequate_and_valid` both true. Missing, malformed, wrong-diagnosis and inadequate plans on eligible cases are failures. Denominator is **E** (eligible count), never silently shrunk.

## CLI

```bash
python scripts/verify_model_plans.py \
  --plans model_a_test_plans.json \
  --cohort test \
  --generation-metadata run_metadata.json \
  --eligibility-manifest path/to/eligibility.json \
  --plan-labels path/to/plan_labels.json
```

Without those two files the adjudicated fields stay unavailable. Synthetic self-labels in unit tests are software checks only, not clinical ground truth.

## Related

- Metric definitions: [metrics.md](metrics.md)
- Protocol: [evaluation_protocol.json](evaluation_protocol.json)
- Rule catalog second human review (separate open item): [rule_signoff.md](rule_signoff.md), [rule_second_review.md](rule_second_review.md)
