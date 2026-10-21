"""Rule interface for the rule catalog.

A rule is a named, sourced constraint over a Plan (and the case facts), expressed as a Z3 Boolean expression that must
hold when the rule applies. Registration enforces the project requirement "rules have IDs and supporting sources".

  applies      when the rule is relevant (for example only for one diagnosis); not applicable = skipped
  requires     plan fields / case facts ('facts.<key>') the constraint needs; if one is missing the rule is
               inconclusive ("insufficient information"), never an automatic pass
  constraint   Z3 expression that must be satisfiable for the plan to comply

See docs/rule_authoring.md for how to add a rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

import z3

from clinverify.plan import Plan

ID_PATTERN = re.compile(r"^R-[A-Z]{2,8}-\d{3}$")     # e.g. R-APP-001


@dataclass(frozen=True)
class Rule:
    id: str                                          # unique, e.g. R-APP-001
    description: str                                 # one sentence: what must hold
    source: str                                      # guideline or paper that justifies the rule (with location)
    requires: tuple[str, ...]                        # Plan fields and 'facts.<key>' the constraint needs
    constraint: Callable[[Plan], z3.BoolRef]
    name: str = ""
    recommendation: str = ""                         # what the source recommends, paraphrased, with statement location
    strength: str = ""                               # strength / quality of the recommendation as stated by the source
    applies_when: str = ""                           # plain-language condition under which the rule applies
    applies: Optional[Callable[[Plan], bool]] = None  # None = always applies
    violation_message: str = ""                      # shown when the rule is violated (also feedback for repair)
    valid_example: Optional[Plan] = None             # synthetic plan that satisfies the rule
    invalid_example: Optional[Plan] = None           # synthetic plan that violates the rule


class RuleCatalog:
    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    def register(self, id: str, description: str, source: str, requires: tuple[str, ...] = (), **extra):
        """Decorator: @catalog.register("R-APP-001", "...", "source", requires=(...), name=..., applies=..., ...)"""
        def wrap(fn: Callable[[Plan], z3.BoolRef]) -> Callable[[Plan], z3.BoolRef]:
            self.add(Rule(id, description, source, tuple(requires), fn, **extra))
            return fn
        return wrap

    def add(self, rule: Rule) -> None:
        if not ID_PATTERN.match(rule.id):
            raise ValueError(f"rule id {rule.id!r} must look like R-APP-001")
        if rule.id in self._rules:
            raise ValueError(f"duplicate rule id {rule.id}")
        if not rule.description.strip():
            raise ValueError(f"{rule.id}: description is empty")
        if not rule.source.strip():
            raise ValueError(f"{rule.id}: every rule needs a supporting source")
        unknown = [f for f in rule.requires if not f.startswith("facts.") and f not in Plan.__dataclass_fields__]
        if unknown:
            raise ValueError(f"{rule.id}: requires unknown Plan fields {unknown}")
        self._rules[rule.id] = rule

    def undocumented(self) -> list[str]:
        """IDs of rules missing a name, recommendation, strength, applicability text, violation message or either example."""
        return [r.id for r in self._rules.values()
                if not (r.name and r.recommendation and r.strength and r.applies_when and r.violation_message and r.valid_example and r.invalid_example)]

    def __iter__(self):
        return iter(self._rules.values())

    def __len__(self) -> int:
        return len(self._rules)

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]
