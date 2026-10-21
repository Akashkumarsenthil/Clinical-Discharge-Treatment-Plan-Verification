# Writing a rule

Rules are the project's central claim: **the team writes them, not the model** (requirement R3). The code only provides the machinery; `src/clinverify/rules/catalog.py` is intentionally empty until the team adds rules.

## What a rule is

A rule is a named, sourced constraint over a `Plan` (`src/clinverify/plan.py`). It returns a Z3 Boolean expression that must hold for the plan to be valid. The verifier reports a rule as **violated** when that expression is unsatisfiable for the plan, and as **inconclusive** when a field the rule needs is not stated in the plan.

| Part | Requirement |
|---|---|
| `id` | unique, format `R-<AREA>-<NNN>` (for example `R-LAB-001`) |
| `description` | one sentence saying what must hold |
| `source` | the guideline, paper or clinical reference that justifies the rule (registration fails without it) |
| `requires` | the `Plan` fields the rule needs |
| function | builds the Z3 expression from the plan |

## Pattern (register one function per rule)

```python
import z3
from clinverify.rules.base import RuleCatalog
catalog = RuleCatalog()   # already created in catalog.py

@catalog.register("R-XXX-001", "what must hold", "reference that justifies it", requires=("discharge_hour",))
def r_xxx_001(plan):
    return z3.IntVal(plan.discharge_hour) >= z3.IntVal(0)
```

Working examples that are **toy rules, not clinical content** are in `tests/toy_rules.py`.

## Checklist before a rule is merged

1. The source is a real reference that someone on the team has read, and the rule matches it. Do not invent thresholds.
2. One valid and one violating synthetic plan are added to the tests.
3. A second team member reviews the rule and the source.
4. Any new `Plan` field the rule needs is added to `plan.py` and to the Model A output specification.
5. Run `python -m pytest tests`, then `python scripts/run_eval.py --plans <labeled plans> --rules clinverify.rules.catalog --seed 298`.

## Design choices the team should confirm

- A plan is counted **valid only if no rule is violated and none is inconclusive**, so a missing field never passes silently.
- Times are integer hours since admission.
- `escape_rate` in the harness is the share of known-violating plans that the verifier lets through (confirm this definition in `docs/metrics.md` before freezing).
