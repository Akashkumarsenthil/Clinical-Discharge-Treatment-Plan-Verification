"""Check a Plan against a rule catalog with Z3 and name every broken rule."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import z3

from clinverify.plan import Plan


@dataclass(frozen=True)
class VerifyResult:
    valid: bool                       # True only if no blocking rule is violated and none is inconclusive (advisory findings do not block)
    violated: tuple[str, ...]         # rule IDs whose constraint is unsatisfiable for this plan (advisory ones included)
    inconclusive: tuple[str, ...]     # rule IDs that apply but lack a required field or case fact
    solve_ms: float                   # solver time for this plan
    not_applicable: tuple[str, ...] = ()                      # rule IDs that do not apply to this plan (including a false condition)
    messages: dict = field(default_factory=dict)             # violated rule ID -> violation message
    advisory: tuple[str, ...] = ()                            # violated rules whose source only suggests (a subset of `violated`)
    advisory_inconclusive: tuple[str, ...] = ()               # inconclusive rules whose source only suggests (a subset of `inconclusive`)

    @property
    def complete(self) -> bool:
        return not self.inconclusive

    @property
    def blocking(self) -> tuple[str, ...]:
        """Violated rules that are not advisory."""
        return tuple(r for r in self.violated if r not in self.advisory)

    @property
    def blocking_inconclusive(self) -> tuple[str, ...]:
        return tuple(r for r in self.inconclusive if r not in self.advisory_inconclusive)

    @property
    def status(self) -> str:
        """'violated' (a blocking rule), 'insufficient_information' (a blocking rule lacks input) or 'valid'.
        Advisory violations and advisory unknowns are reported in `advisory` / `advisory_inconclusive` and do not change the status."""
        if self.blocking:
            return "violated"
        return "insufficient_information" if self.blocking_inconclusive else "valid"


def _condition_false(rule, plan: Plan) -> bool:
    """True if a case fact named in the rule's condition is known and contradicts it."""
    for key, value in rule.condition_facts:
        known = plan.facts.get(key)
        if known is not None and bool(known) != value:
            return True
    return False


def verify(plan: Plan, rules) -> VerifyResult:
    violated, inconclusive, skipped, messages, advisory, adv_inconclusive = [], [], [], {}, [], []
    start = time.perf_counter()
    for rule in rules:
        if rule.applies is not None and not rule.applies(plan):
            skipped.append(rule.id)
            continue
        if _condition_false(rule, plan):
            skipped.append(rule.id)
            continue
        needed = rule.requires_for(plan) if rule.requires_for else rule.requires
        if any(not plan.has(name) for name in needed):
            inconclusive.append(rule.id)
            if rule.advisory:
                adv_inconclusive.append(rule.id)
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
    blocking_violated = [r for r in violated if r not in advisory]
    blocking_inconclusive = [r for r in inconclusive if r not in adv_inconclusive]
    return VerifyResult(valid=not blocking_violated and not blocking_inconclusive, violated=tuple(violated),
                        inconclusive=tuple(inconclusive), solve_ms=ms, not_applicable=tuple(skipped), messages=messages,
                        advisory=tuple(advisory), advisory_inconclusive=tuple(adv_inconclusive))
