# Writing a rule

Rules are the project's central claim: **the team writes them, not the model** (requirement R3). The code only provides the machinery; `src/clinverify/rules/catalog.py` holds a first DRAFT set (see `docs/rule_catalog.md`) that the team must review and extend.

## What a rule is

A rule is a named, sourced constraint over a `Plan` (`src/clinverify/plan.py`) and the case facts. It returns a Z3 Boolean expression that must hold when the rule applies. The verifier reports a rule as **violated** when that expression is unsatisfiable for the plan, **inconclusive** ("insufficient information") when an input it needs is missing, and skips it when it does not apply.

| Part | Requirement |
|---|---|
| `id` | unique, format `R-<AREA>-<NNN>` (for example `R-APP-001`) |
| `name`, `description` | a short name and one sentence saying what must hold |
| `source` | the guideline or paper **with the statement number or section** (registration fails without a source) |
| `recommendation` | what the source recommends, paraphrased |
| `strength` | the strength / quality of the recommendation as the source states it |
| `applies` / `applies_when` | when the rule is relevant, as code and as plain language |
| `requires` | plan fields and case facts (`facts.<key>`) the constraint needs |
| `violation_message` | what the plan did wrong; also the feedback for the repair loop |
| `valid_example`, `invalid_example` | one synthetic plan that satisfies the rule and one that violates only this rule |
| function | builds the Z3 expression from the plan |

See `src/clinverify/rules/catalog.py` for 12 complete examples, and `docs/rule_catalog.md` (generated) for the table.

## Checklist before a rule is merged

1. The source is a real reference whose full text someone on the team has read, and the rule matches the cited statement. Do not invent thresholds.
2. The rule's valid and invalid examples are added (the tests check that the invalid one breaks only this rule), then run `python scripts/make_catalog_labeled_plans.py` and `python scripts/build_rule_catalog_doc.py`.
3. A second team member reviews the rule and the source.
4. Any new `Plan` field the rule needs is added to `plan.py` and to the Model A output specification.
5. Run `python -m pytest tests`, then `python scripts/run_eval.py --plans <labeled plans> --rules clinverify.rules.catalog --seed 298`.

## Design choices the team should confirm

- A plan is counted **valid only if no rule is violated and none is inconclusive**, so a missing field never passes silently.
- Times are integer hours since admission.
- `escape_rate` in the harness is the share of known-violating plans that the verifier lets through (confirm this definition in `docs/metrics.md` before freezing).


## Conditions and unknown facts (v2.1)

- `condition_facts=(("complicated", False),)`: the case-fact values under which the rule's condition holds. If a fact is known and different, the rule is **not applicable** (it is not counted as a pass). If the fact is unknown, the rule stays applicable and is inconclusive.
- `requires_for=fn(plan)`: optional, returns the fields this plan needs, so an unknown that cannot change the outcome does not block a decidable check (see R-DIV-003).
- `advisory=True`: a violation is reported but does not make the plan invalid.
