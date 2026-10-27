"""Independent plan-label scorer: scores only when humans supply complete files."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.eval.adjudication import (
    apply_adjudication,
    manifest_sha256,
    score_adjudicated_validity,
    validate_eligibility_manifest,
    validate_plan_labels,
)
from clinverify.eval.model_run import verify_model_plans
from clinverify.rules.catalog import catalog

FACTS = {
    1: {"pathology": "appendicitis", "facts": {"complicated": False}},
    2: {"pathology": "appendicitis", "facts": {"complicated": True}},
    3: {"pathology": "diverticulitis", "facts": {"complicated": False, "alarm_symptoms": False}},
    4: {"pathology": "cholecystitis", "facts": {}},
}


def app(case_id=1, days=0):
    return {
        "case_id": case_id,
        "diagnosis": "appendicitis",
        "treatments": ["appendectomy", "preoperative_antibiotic"],
        "postop_antibiotic_days": days,
    }


def _eligibility(ids, *, ineligible=()):
    ineligible = set(ineligible)
    return {
        "schema_version": 1,
        "catalog_version": "2.1",
        "reviewer": "T1",
        "review_date": "2026-10-27",
        "blind_to_plans": True,
        "cases": [
            {"case_id": cid, "eligible": cid not in ineligible,
             "reason": "insufficient record" if cid in ineligible else ""}
            for cid in ids
        ],
    }


def _labels(eligible_ids, manifest_hash, *, success=None, unresolved=(), blocking=None):
    success = set(success or [])
    unresolved = set(unresolved)
    blocking = blocking or {}
    rows = []
    for cid in eligible_ids:
        if cid in unresolved:
            rows.append({
                "case_id": cid,
                "diagnosis_correct": None,
                "clinically_adequate_and_valid": None,
                "blocking_invalid": None,
                "blocking_rule_ids": [],
                "notes": "",
            })
        else:
            ok = cid in success
            rows.append({
                "case_id": cid,
                "diagnosis_correct": True,
                "clinically_adequate_and_valid": ok,
                "blocking_invalid": blocking.get(cid),
                "blocking_rule_ids": [],
                "notes": "",
            })
    return {
        "schema_version": 1,
        "eligibility_manifest_sha256": manifest_hash,
        "reviewer": "T2",
        "review_date": "2026-10-27",
        "labels": rows,
    }


def test_without_labels_runner_stays_unavailable():
    result = verify_model_plans([app()], FACTS, catalog, expected_case_ids=[1])
    assert result["adjudicated_treatment_validity_rate"] is None
    assert result["adjudication_status"] == "unavailable_no_independent_plan_labels_loaded"


def test_eligibility_must_cover_exactly_the_covered_cohort():
    covered = {1, 2, 3}
    validate_eligibility_manifest(_eligibility([1, 2, 3]), covered_case_ids=covered)
    try:
        validate_eligibility_manifest(_eligibility([1, 2]), covered_case_ids=covered)
        assert False, "expected ValueError"
    except ValueError as err:
        assert "exactly the covered cohort" in str(err)


def test_unresolved_labels_block_the_rate():
    covered = {1, 2}
    elig = _eligibility([1, 2])
    digest = manifest_sha256(elig)
    labs = validate_plan_labels(
        _labels([1, 2], digest, success={1}, unresolved={2}),
        eligible_case_ids={1, 2},
        expected_manifest_sha256=digest,
    )
    scored = score_adjudicated_validity([1, 2], labs["by_id"])
    assert scored["adjudicated_treatment_validity_rate"] is None
    assert scored["adjudication_status"] == "unavailable_unresolved_labels"


def test_complete_labels_score_adjudicated_rate_and_escape():
    covered = {1, 2, 3}
    elig_doc = _eligibility([1, 2, 3], ineligible={3})
    digest = manifest_sha256(elig_doc)
    labels_doc = _labels([1, 2], digest, success={1}, blocking={1: False, 2: True})
    outputs = [app(1), app(2, days=0)]  # both likely valid under facts depending on complicated
    # case 2 complicated needs postop antibiotics under catalog — days=0 may violate
    summary = verify_model_plans(
        outputs, FACTS, catalog, expected_case_ids=[1, 2, 3, 4],
        supported_diagnoses={"appendicitis", "pancreatitis", "diverticulitis"},
        eligibility_manifest=elig_doc, plan_labels=labels_doc, catalog_version="2.1",
    )
    assert summary["adjudication_status"] == "scored_from_independent_labels"
    assert summary["n_eligible"] == 2
    assert summary["n_adjudicated_success"] == 1
    assert summary["adjudicated_treatment_validity_rate"] == 0.5
    assert "adjudication" in summary
    assert summary["adjudication"]["eligibility"]["n_ineligible"] == 1


def test_partial_inputs_do_not_score():
    summary = {"per_case": []}
    apply_adjudication(
        summary,
        eligibility_manifest=_eligibility([1]),
        plan_labels=None,
        covered_case_ids={1},
    )
    assert summary["adjudication_status"] == "unavailable_incomplete_adjudication_inputs"
    assert summary["adjudicated_treatment_validity_rate"] is None
