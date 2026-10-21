"""Check a Plan against a rule catalog with Z3 and name every broken rule."""
from __future__ import annotations

import time
from dataclasses import dataclass

import z3

from clinverify.plan import Plan
from clinverify.rules.base import Rule


@dataclass(frozen=True)
class VerifyResult:
    valid: bool                       # True only if no rule is violated and none is inconclusive
    violated: tuple[str, ...]         # rule IDs whose constraint is unsatisfiable for this plan
    inconclusive: tuple[str, ...]     # rule IDs that could not be evaluated because a required field is missing
    solve_ms: float                   # solver time for this plan

    @property
    def complete(self) -> bool:
        return not self.inconclusive


def verify(plan: Plan, rules) -> VerifyResult:
    violated, inconclusive = [], []
    start = time.perf_counter()
    for rule in rules:
        if any(not plan.has(field) for field in rule.requires):
            inconclusive.append(rule.id)
            continue
        solver = z3.Solver()
        solver.add(rule.constraint(plan))
        outcome = solver.check()
        if outcome == z3.unsat:
            violated.append(rule.id)
        elif outcome == z3.unknown:
            raise RuntimeError(f"Z3 returned unknown for {rule.id}: {solver.reason_unknown()}")
    ms = (time.perf_counter() - start) * 1000
    return VerifyResult(valid=not violated and not inconclusive, violated=tuple(violated),
                        inconclusive=tuple(inconclusive), solve_ms=ms)
