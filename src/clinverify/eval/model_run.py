"""Verify a batch of Model A plans against the rule catalog and summarize the result (no patient text)."""
from __future__ import annotations

from collections import Counter

import numpy as np
from clinverify.data.case_loader import plan_from_model_output
from clinverify.eval.harness import per_rule_counts
from clinverify.verifier.z3_verifier import verify


def verify_model_plans(outputs: list[dict], case_facts: dict[int, dict], rules, *, expected_case_ids=None,
                       supported_diagnoses=None, eligibility_manifest=None, plan_labels=None,
                       catalog_version=None) -> dict:
    """Score a submission; a fixed cohort is mandatory for validation/test reporting.

    Without expected_case_ids this remains a submission-only diagnostic (legacy
    pilot behavior). With a cohort, omitted outputs count as failures and duplicate
    or out-of-cohort IDs invalidate the run rather than changing its denominator.
    """
    if not isinstance(outputs, list):
        raise ValueError("outputs must be a JSON list")
    if supported_diagnoses is None:
        from clinverify.rules.catalog import COVERED_DIAGNOSES
        supported_diagnoses = COVERED_DIAGNOSES
    supported_diagnoses = set(supported_diagnoses)
    expected = None
    if expected_case_ids is not None:
        ids = list(expected_case_ids)
        if any(type(h) is not int for h in ids) or len(set(ids)) != len(ids):
            raise ValueError("expected cohort must contain unique integer case IDs")
        expected = set(ids)
        if not expected <= set(case_facts):
            raise ValueError("record facts are missing for an expected cohort case")
        submitted = []
        for out in outputs:
            if not isinstance(out, dict) or type(out.get("case_id")) is not int:
                raise ValueError("fixed-cohort outputs must have an integer case_id; omit failed generations instead")
            if out["case_id"] not in expected:
                raise ValueError("submission contains an out-of-cohort case")
            submitted.append(out["case_id"])
        if len(set(submitted)) != len(submitted):
            raise ValueError("duplicate case IDs in a fixed-cohort submission")
    rules = list(rules)
    clinical_ids = {r.id for r in rules if not r.id.startswith("R-GEN-")}
    blocking_clinical_ids = {r.id for r in rules if r.id in clinical_ids and not r.advisory}
    per_case, rule_counts, status_counts = [], Counter(), Counter()
    unparseable, wrong_diagnosis, times, results = [], 0, [], []
    correct_results = []
    supported_correct_results = []
    treatment_status = Counter()
    checked_treatment_status = Counter()
    supported_checked_valid = supported_accepted_without_checks = 0
    empty_treatment_plans = 0
    supported_valid = supported_raw_valid = correct_supported_n = 0
    scheduled = list(expected) if expected is not None else [o.get("case_id") if isinstance(o, dict) else None for o in outputs]
    supported_n = sum(case_facts.get(h, {}).get("pathology") in supported_diagnoses
                      for h in scheduled if type(h) is int)
    valid_without_clinical_checks = 0
    correct_valid = correct_n = 0
    for out in outputs:
        if not isinstance(out, dict):
            unparseable.append({"case_id": None, "error": "plan must be an object"})
            continue
        # Diagnosis is scored independently of whether the treatment fields parse.
        raw_id = out.get("case_id")
        record = case_facts.get(raw_id) if type(raw_id) is int else None
        correct = record is not None and out.get("diagnosis") == record["pathology"]
        supported = record is not None and record["pathology"] in supported_diagnoses
        correct_n += correct
        correct_supported_n += correct and supported
        try:
            plan = plan_from_model_output(out, case_facts)
        except (ValueError, TypeError) as err:
            unparseable.append({"case_id": out.get("case_id"), "error": str(err)})
            if supported:
                treatment_status["unparseable"] += 1
                checked_treatment_status["unparseable"] += 1
            continue
        res = verify(plan, rules)
        results.append(res)
        status_counts[res.status] += 1
        rule_counts.update(res.violated)
        times.append(res.solve_ms)
        wrong_diagnosis += not correct
        correct_valid += correct and res.valid
        if correct:
            correct_results.append(res)
        checked = clinical_ids - set(res.not_applicable) - set(res.inconclusive)
        blocking_checked = blocking_clinical_ids & checked
        checked_status = ("accepted_with_decided_blocking_clinical_check" if blocking_checked
                          else "accepted_without_decided_blocking_clinical_check") if res.valid else res.status
        empty_treatment_plans += not plan.treatments
        if supported:
            supported_raw_valid += res.valid
            supported_valid += correct and res.valid
            treatment_status[res.status if correct else "wrong_diagnosis"] += 1
            checked_treatment_status[checked_status if correct else "wrong_diagnosis"] += 1
            supported_checked_valid += correct and res.valid and bool(blocking_checked)
            supported_accepted_without_checks += correct and res.valid and not blocking_checked
            if correct:
                supported_correct_results.append(res)
        valid_without_clinical_checks += res.valid and not checked
        per_case.append({"case_id": plan.case_id, "status": res.status, "violated": list(res.violated),
                         "diagnosis_correct": correct, "advisory": list(res.advisory), "inconclusive": list(res.inconclusive),
                         "treatment_evaluation_status": (res.status if correct else "wrong_diagnosis") if supported else "unsupported",
                         "checked_treatment_evaluation_status": (checked_status if correct else "wrong_diagnosis") if supported else "unsupported",
                         "n_decided_blocking_clinical_checks": len(blocking_checked),
                         "advisory_inconclusive": list(res.advisory_inconclusive)})
    n_missing = len(expected - {out["case_id"] for out in outputs}) if expected is not None else 0
    n = len(expected) if expected is not None else len(outputs)
    if unparseable:
        status_counts["unparseable"] = len(unparseable)
    if n_missing:
        status_counts["missing_output"] = n_missing
        missing_supported = sum(case_facts[h]["pathology"] in supported_diagnoses
                                for h in expected - {o["case_id"] for o in outputs})
        if missing_supported:
            treatment_status["missing_output"] = missing_supported
            checked_treatment_status["missing_output"] = missing_supported
    summary = {
        "n_plans": n, "n_unparseable": len(unparseable), "n_wrong_diagnosis": wrong_diagnosis,
        "n_submitted": len(outputs), "n_missing_outputs": n_missing,
        "scoring_population": "fixed_cohort" if expected is not None else "submitted_outputs_only_pilot",
        "n_verified": len(results), "n_correct_diagnosis": correct_n,
        "n_supported_cases": supported_n, "n_unsupported_cases": n - supported_n,
        "supported_treatment_validity_rate": (supported_valid / supported_n) if supported_n else None,
        # A scope guard, skipped rules, or advisory-only checks cannot earn this credit.
        # This still measures catalog acceptance, not completeness or clinical safety.
        "supported_checked_acceptance_rate": (supported_checked_valid / supported_n) if supported_n else None,
        "n_supported_checked_accepted": supported_checked_valid,
        "n_supported_accepted_without_decided_blocking_clinical_check": supported_accepted_without_checks,
        "checked_treatment_status": dict(checked_treatment_status),
        "adjudicated_treatment_validity_rate": None,
        "adjudication_status": "unavailable_no_independent_plan_labels_loaded",
        "n_empty_treatment_plans": empty_treatment_plans,
        "supported_rule_compliance_rate": (supported_raw_valid / supported_n) if supported_n else None,
        "supported_treatment_validity_given_correct_diagnosis": (supported_valid / correct_supported_n) if correct_supported_n else None,
        "n_correct_diagnosis_supported": correct_supported_n, "n_supported_accepted_plans": supported_valid,
        "treatment_status": dict(treatment_status),
        "status": dict(status_counts), "validity_rate": (status_counts["valid"] / n) if n else None,
        # diagnosis and treatment are scored separately: a plan for the wrong diagnosis is checked against facts of the
        # real condition, so its validity says little about the treatment. Report both rates.
        "diagnosis_accuracy": (correct_n / n) if n else None,
        "validity_rate_diagnosis_correct": (correct_valid / correct_n) if correct_n else None,
        "joint_success_rate": (correct_valid / n) if n else None,
        "n_valid_without_clinical_checks": valid_without_clinical_checks,
        "n_with_advisory_finding": sum(bool(r.advisory) for r in results),
        "n_with_advisory_unknown": sum(bool(r.advisory_inconclusive) for r in results),
        "violations_by_rule": dict(rule_counts.most_common()),
        "per_rule": per_rule_counts(results, rules),       # not_applicable / unknown / passed / violated per rule
        "per_rule_denominator": len(results),
        "per_rule_diagnosis_correct": per_rule_counts(correct_results, rules),
        "per_rule_diagnosis_correct_denominator": len(correct_results),
        "per_rule_supported_correct": per_rule_counts(supported_correct_results, rules),
        "per_rule_supported_correct_denominator": len(supported_correct_results),
        "rule_advisory": {r.id: r.advisory for r in rules},
        "solver_ms_mean": (sum(times) / len(times)) if times else None,
        "solver_ms_p95": float(np.percentile(times, 95)) if times else None,
        "unparseable": unparseable, "per_case": per_case,
    }
    if eligibility_manifest is not None or plan_labels is not None:
        from clinverify.eval.adjudication import apply_adjudication
        covered = {
            h for h in (expected if expected is not None else scheduled)
            if type(h) is int and case_facts.get(h, {}).get("pathology") in supported_diagnoses
        }
        apply_adjudication(
            summary,
            eligibility_manifest=eligibility_manifest,
            plan_labels=plan_labels,
            covered_case_ids=covered,
            catalog_version=catalog_version,
        )
    return summary
