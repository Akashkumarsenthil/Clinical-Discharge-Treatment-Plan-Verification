# Evaluation metrics (DRAFT: not frozen)

Source: project abstract and Workbook 1 (sections 1.2 and 2.2.2). Template rule: metrics are committed **before** any results exist and are not revised after results are seen. This file becomes the committed record once the team marks it frozen (tag the commit `metrics-frozen`).

## Primary metric and targets (from the abstract)

| Metric | Meaning | Target | Measured on |
|---|---|---|---|
| Plan validity rate | share of generated plans that satisfy the team-written rule set | **>= 0.85** | fixed 100-case held-out test split, grouped by patient (`data/splits/ext_cdm_splits_v2.json`) |
| Constraint-violation escape rate | share of rule-violating plans that the verifier fails to flag | **<= 0.05** | same 100-case split |

## Secondary metrics (named in the abstract; targets not yet set)

| Metric | Meaning | Target |
|---|---|---|
| Repair success rate | share of rejected plans that pass after solver-feedback repair (Model C, 298B) | to be set by the team |
| Translation fidelity | agreement between the formal specification and the intended meaning of the note/plan (Model B, 298B) | to be set by the team |
| Solver cost | verifier time per plan (and repair rounds, where used) | to be set by the team |

## Open items before freezing

- [ ] Targets for repair success, translation fidelity and solver cost
- [ ] Exact definition of the escape-rate numerator and denominator (this draft uses: known-violating plans that the verifier passes / all known-violating plans)
- [ ] Team sign-off, then tag the commit `metrics-frozen`

## Notes

- Validity measures compliance with our formal rules. It does not prove a plan is clinically correct.
- The Hager et al. (2024) baseline number (54.9%, Fig. 3) is diagnostic accuracy. It is a different task and is not compared directly with plan validity.
- Exact definitions of the escape-rate numerator and denominator need to be confirmed by the team before freezing.
- Results will be reported over multiple seeds with the number of runs stated.
