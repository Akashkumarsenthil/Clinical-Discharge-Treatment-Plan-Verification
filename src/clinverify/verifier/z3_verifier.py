"""Check a Plan against a rule catalog with Z3 and name every broken rule."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import z3

from clinverify.plan import Plan


@dataclass(frozen=True)
class VerifyResult:
    valid: bool                       # True only if no rule is violated and none is inconclusive
    violated: tuple[str, ...]         # rule IDs whose constraint is unsatisfiable for this plan
    inconclusive: tuple[str, ...]     # rule IDs that apply but lack a required field or case fact
    solve_ms: float                   # solver time for this plan
    not_applicable: tuple[str, ...] = ()                      # rule IDs that do not apply to this plan
    messages: dict = field(default_factory=dict)             # violated rule ID -> violation message
    advisory: tuple[str, ...] = ()                            # violated rules whose source only suggests (a subset of `violated`)

    @property
    def complete(self) -> bool:
        return not self.inconclusive

    @property
    def blocking(self) -> tuple[str, ...]:
        """Violated rules that are not advisory."""
        return tuple(r for r in self.violated if r not in self.advisory)

    @property
    def status(self) -> str:
        """'violated', 'insufficient_information' or 'valid'."""
        if self.violated:
            return "violated"
        return "insufficient_information" if self.inconclusive else "valid"


def verify(plan: Plan, rules) -> VerifyResult:
    violated, inconclusive, skipped, messages, advisory = [], [], [], {}, []
    start = time.perf_counter()
    for rule in rules:
        if rule.applies is not None and not rule.applies(plan):
            skipped.append(rule.id)
            continue
        if any(not plan.has(name) for name in rule.requires):
            inconclusive.append(rule.id)
            continue
        solver = z3.Solver()
        solver.add(rule.constraint(plan))
        outcome = solver.check()
        if outcome == z3.unsat:
            violated.append(rule.id)
            messages[rule.id] = ("(advisory) " if rule.advisory else "") + (rule.violation_message or rule.description)
            if rule.advisory:
                advisory.append(rule.id)
        elif outcome == z3.unknown:
            raise RuntimeError(f"Z3 returned unknown for {rule.id}: {solver.reason_unknown()}")
    ms = (time.perf_counter() - start) * 1000
    return VerifyResult(valid=not violated and not inconclusive, violated=tuple(violated), inconclusive=tuple(inconclusive),
                        solve_ms=ms, not_applicable=tuple(skipped), messages=messages, advisory=tuple(advisory))
