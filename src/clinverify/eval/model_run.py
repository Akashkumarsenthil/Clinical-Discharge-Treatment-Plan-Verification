"""Verify a batch of Model A plans against the rule catalog and summarize the result (no patient text)."""
from __future__ import annotations

from collections import Counter

from clinverify.data.case_loader import plan_from_model_output
from clinverify.verifier.z3_verifier import verify


def verify_model_plans(outputs: list[dict], case_facts: dict[int, dict], rules) -> dict:
    rules = list(rules)
    per_case, rule_counts, status_counts = [], Counter(), Counter()
    unparseable, wrong_diagnosis, times = [], 0, []
    for out in outputs:
        try:
            plan = plan_from_model_output(out, case_facts)
        except (ValueError, TypeError) as err:
            unparseable.append({"case_id": out.get("case_id"), "error": str(err)})
            continue
        res = verify(plan, rules)
        status_counts[res.status] += 1
        rule_counts.update(res.violated)
        times.append(res.solve_ms)
        wrong_diagnosis += plan.diagnosis != case_facts[plan.case_id]["pathology"]
        per_case.append({"case_id": plan.case_id, "status": res.status, "violated": list(res.violated),
                         "advisory": list(res.advisory), "inconclusive": list(res.inconclusive)})
    n = len(outputs)
    return {
        "n_plans": n, "n_unparseable": len(unparseable), "n_wrong_diagnosis": wrong_diagnosis,
        "status": dict(status_counts), "validity_rate": (status_counts["valid"] / n) if n else None,
        "violations_by_rule": dict(rule_counts.most_common()),
        "solver_ms_mean": (sum(times) / len(times)) if times else None,
        "unparseable": unparseable, "per_case": per_case,
    }
