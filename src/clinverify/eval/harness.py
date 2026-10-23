"""Evaluation harness: score a verifier on labeled plans and report the project's primary metrics.

Each labeled plan carries the rule IDs it is known to violate (empty = known valid). The harness reports:
  validity_rate      share of plans the verifier judges valid
  escape_rate        share of known-violating plans the verifier lets through   (target <= 0.05)
  false_reject_rate  share of known-valid plans the verifier rejects
  exact_rule_match   share of known-violating plans where the flagged rules equal the known violations
  solver_ms          mean and 95th percentile verification time per plan
Rates come with 95% bootstrap intervals computed with the recorded seed.
"""
from __future__ import annotations

import numpy as np

from clinverify.plan import Plan
from clinverify.verifier.z3_verifier import verify


def _rate_ci(flags: list[bool], rng: np.random.Generator, n_boot: int = 1000) -> dict:
    if not flags:
        return {"rate": None, "ci95": [None, None], "n": 0}
    arr = np.array(flags, dtype=float)
    boots = [rng.choice(arr, size=len(arr), replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"rate": float(arr.mean()), "ci95": [float(lo), float(hi)], "n": int(len(arr))}


def per_rule_counts(results, rules) -> dict:
    """Per rule: how many plans it did not apply to, lacked input for (unknown), passed, or violated."""
    table = {r.id: {"not_applicable": 0, "unknown": 0, "passed": 0, "violated": 0} for r in rules}
    for res in results:
        for rid, row in table.items():
            if rid in res.not_applicable:
                row["not_applicable"] += 1
            elif rid in res.inconclusive:
                row["unknown"] += 1
            elif rid in res.violated:
                row["violated"] += 1
            else:
                row["passed"] += 1
    return table


def evaluate(labeled: list[tuple[Plan, set[str]]], rules, seed: int) -> dict:
    """Score labeled plans. A plan is 'known violating' if it breaks a blocking rule; advisory rules are suggestions,
    so a plan whose only expected violations are advisory is expected to be valid (the advisory finding is still reported)."""
    rules = list(rules)
    advisory_ids = {r.id for r in rules if r.advisory}
    rng = np.random.default_rng(seed)
    results = [(verify(plan, rules), set(expected) - advisory_ids) for plan, expected in labeled]
    violating = [(r, e) for r, e in results if e]
    clean = [(r, e) for r, e in results if not e]
    times = [r.solve_ms for r, _ in results] or [0.0]
    return {
        "n_plans": len(results),
        "n_known_violating": len(violating),
        "n_known_valid": len(clean),
        "validity_rate": _rate_ci([r.valid for r, _ in results], rng),
        "escape_rate": _rate_ci([r.valid for r, _ in violating], rng),
        "false_reject_rate": _rate_ci([not r.valid for r, _ in clean], rng),
        "exact_rule_match": _rate_ci([set(r.blocking) == e for r, e in violating], rng),
        "n_with_advisory_finding": sum(bool(r.advisory) for r, _ in results),
        "solver_ms": {"mean": float(np.mean(times)), "p95": float(np.percentile(times, 95))},
        "n_rules": len(rules),
        "per_rule": per_rule_counts([r for r, _ in results], rules),
    }
