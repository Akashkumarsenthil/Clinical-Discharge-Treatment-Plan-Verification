"""Frozen metric definitions; synthetic data only."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.eval.model_run import verify_model_plans
from clinverify.eval.protocol import cohort_ids, load_protocol, treatment_cohort_record, validate_generation_metadata
from clinverify.rules.catalog import catalog

FACTS = {
    1: {"pathology": "appendicitis", "facts": {"complicated": False}},
    2: {"pathology": "appendicitis", "facts": {"complicated": True}},
    3: {"pathology": "diverticulitis", "facts": {"complicated": False}},
    4: {"pathology": "cholecystitis", "facts": {}},
}


def app(case_id=1, days=0):
    return {"case_id": case_id, "diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"],
            "postop_antibiotic_days": days}


def test_missing_generations_remain_failures_in_the_fixed_denominator():
    result = verify_model_plans([app()], FACTS, catalog, expected_case_ids=[1, 2])
    assert result["n_plans"] == 2 and result["n_submitted"] == 1 and result["n_missing_outputs"] == 1
    assert result["validity_rate"] == result["diagnosis_accuracy"] == result["joint_success_rate"] == 0.5
    assert result["status"] == {"valid": 1, "missing_output": 1}
    assert result["per_rule_denominator"] == 1
    assert all(sum(counts.values()) == 1 for counts in result["per_rule"].values())


@pytest.mark.parametrize("outputs", [[app(), app()], [{**app(), "case_id": 99}],
                                      [{**app(), "case_id": True}], [{**app(), "case_id": "1"}], [None]])
def test_fixed_cohort_rejects_duplicate_unknown_or_unidentifiable_cases(outputs):
    with pytest.raises(ValueError):
        verify_model_plans(outputs, FACTS, catalog, expected_case_ids=[1, 2])


def test_missing_record_facts_are_a_data_error_not_a_missing_model_output():
    with pytest.raises(ValueError, match="record facts"):
        verify_model_plans([], FACTS, catalog, expected_case_ids=[99])


def test_diagnosis_accuracy_is_independent_of_treatment_parse_failure():
    malformed = {**app(), "treatments": ["not_a_canonical_treatment"]}
    result = verify_model_plans([malformed], FACTS, catalog, expected_case_ids=[1])
    assert result["diagnosis_accuracy"] == 1.0 and result["n_unparseable"] == 1
    assert result["validity_rate"] == result["validity_rate_diagnosis_correct"] == result["joint_success_rate"] == 0.0


def test_advisory_violations_and_unknowns_do_not_block_but_remain_reported():
    result = verify_model_plans([app(2, days=7), {"case_id": 3, "diagnosis": "diverticulitis", "treatments": []}],
                                FACTS, catalog, expected_case_ids=[2, 3])
    assert result["validity_rate"] == 1.0
    assert result["n_with_advisory_finding"] == result["n_with_advisory_unknown"] == 1
    assert result["per_rule"]["R-APP-003"]["violated"] == 1
    assert result["per_rule"]["R-DIV-003"]["unknown"] == 1
    assert result["rule_advisory"]["R-APP-003"] is True


def test_wrong_diagnosis_cannot_improve_joint_or_correct_diagnosis_metrics():
    result = verify_model_plans([{"case_id": 1, "diagnosis": "diverticulitis", "treatments": []}],
                                FACTS, catalog, expected_case_ids=[1])
    assert result["validity_rate"] == 1.0  # rule compliance alone is not clinical correctness
    assert result["diagnosis_accuracy"] == result["joint_success_rate"] == 0.0
    assert result["validity_rate_diagnosis_correct"] is None
    assert result["n_valid_without_clinical_checks"] == 1
    assert result["per_rule_diagnosis_correct_denominator"] == 0


def test_unsupported_pathology_is_retained_and_not_silently_removed():
    result = verify_model_plans([{"case_id": 4, "diagnosis": "cholecystitis", "treatments": []}],
                                FACTS, catalog, expected_case_ids=[4])
    assert result["diagnosis_accuracy"] == 1.0 and result["validity_rate"] == 0.0
    assert result["violations_by_rule"] == {"R-GEN-001": 1}
    assert result["n_unsupported_cases"] == 1 and result["n_supported_cases"] == 0
    assert result["supported_treatment_validity_rate"] is None
    assert result["per_case"][0]["treatment_evaluation_status"] == "unsupported"


def test_zero_denominators_are_unavailable_not_zero():
    result = verify_model_plans([], {}, catalog, expected_case_ids=[])
    assert all(result[k] is None for k in ("diagnosis_accuracy", "validity_rate", "joint_success_rate", "validity_rate_diagnosis_correct"))


def test_frozen_split_hash_and_cohort_sizes():
    protocol = load_protocol()
    assert protocol["definition_status"] == "frozen" and protocol["catalog_version"] == "2.1"
    assert len(cohort_ids("test")) == 100 and len(cohort_ids("validation")) == 460
    assert set(cohort_ids("test")).isdisjoint(cohort_ids("validation"))
    assert cohort_ids("pilot") is None


def test_changed_split_cannot_be_scored_under_the_existing_protocol(tmp_path):
    (tmp_path / "docs").mkdir()
    protocol = load_protocol()
    (tmp_path / "docs/evaluation_protocol.json").write_text(json.dumps(protocol))
    split = tmp_path / protocol["split_file"]
    split.parent.mkdir(parents=True)
    split.write_text("{}")
    with pytest.raises(ValueError, match="frozen protocol"):
        cohort_ids("test", tmp_path)


def test_formal_test_requires_exact_generation_configuration():
    metadata = {"model": "synthetic-example", "model_digest": "example-version", "prompt_sha256": "a" * 64,
                "seed": 298, "temperature": 0, "top_p": 1, "max_new_tokens": 256}
    validate_generation_metadata(metadata, load_protocol())
    for bad in (None, {}, {**metadata, "seed": 42}, {**metadata, "prompt_sha256": "unknown"},
                {**metadata, "temperature": float("nan")}, {**metadata, "top_p": 0}):
        with pytest.raises(ValueError):
            validate_generation_metadata(bad, load_protocol())


def test_primary_treatment_rate_uses_reference_scope_not_the_models_diagnosis():
    outputs = [app(), {"case_id": 4, "diagnosis": "cholecystitis", "treatments": []}]
    result = verify_model_plans(outputs, FACTS, catalog, expected_case_ids=[1, 4])
    assert result["diagnosis_accuracy"] == 1.0
    assert result["n_supported_cases"] == result["n_unsupported_cases"] == 1
    assert result["supported_treatment_validity_rate"] == 1.0
    assert result["joint_success_rate"] == 0.5
    assert result["treatment_status"] == {"valid": 1}
    assert result["per_rule_supported_correct_denominator"] == 1
    # Misdiagnosing an unsupported reference case cannot make it supported.
    result = verify_model_plans([{**app(), "case_id": 4}], FACTS, catalog, expected_case_ids=[4])
    assert result["n_supported_cases"] == 0 and result["supported_treatment_validity_rate"] is None


def test_missing_supported_generation_is_not_excluded_by_scope_filtering():
    result = verify_model_plans([{"case_id": 4, "diagnosis": "cholecystitis", "treatments": []}],
                                FACTS, catalog, expected_case_ids=[1, 4])
    assert result["supported_treatment_validity_rate"] == 0.0
    assert result["treatment_status"] == {"missing_output": 1}
    assert sum(result["treatment_status"].values()) == result["n_supported_cases"]


def test_primary_treatment_rate_never_credits_a_wrong_diagnosis():
    result = verify_model_plans([{"case_id": 1, "diagnosis": "diverticulitis", "treatments": []}],
                                FACTS, catalog, expected_case_ids=[1])
    assert result["supported_rule_compliance_rate"] == 1.0
    assert result["supported_treatment_validity_rate"] == 0.0
    assert result["treatment_status"] == {"wrong_diagnosis": 1}


def test_formal_treatment_membership_hash_cannot_be_replaced_by_another_cohort():
    with pytest.raises(ValueError, match="73-case"):
        treatment_cohort_record([1, 4], FACTS, load_protocol(), formal_test=True)


def test_missing_cohort_facts_fail_before_computing_any_scope_denominator():
    with pytest.raises(ValueError, match="record facts"):
        treatment_cohort_record([99], FACTS, load_protocol())


def test_cli_smoke_test_writes_provenance_and_keeps_parser_text_out_of_console(tmp_path):
    import os
    import subprocess
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps(FACTS))
    plans = tmp_path / "plans.json"
    plans.write_text(json.dumps([app(), {**app(2), "treatments": ["synthetic_private_parser_marker"]}]))
    out_dir = tmp_path / "runs"
    run = subprocess.run([sys.executable, str(ROOT / "scripts/verify_model_plans.py"), "--plans", str(plans),
                          "--facts-json", str(facts), "--out", str(out_dir)],
                         cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert run.returncode == 0, run.stderr
    assert "synthetic_private_parser_marker" not in run.stdout
    saved = json.loads(next(out_dir.glob("*.json")).read_text())
    assert saved["evaluation"]["protocol_version"] == "1.1"
    assert saved["evaluation"]["cohort"] == "pilot"
    assert saved["diagnosis_accuracy"] == 1.0 and saved["supported_treatment_validity_rate"] == 0.5


def test_cli_refuses_formal_test_without_generation_metadata(tmp_path):
    import os
    import subprocess
    plans = tmp_path / "plans.json"
    plans.write_text("[]")
    run = subprocess.run([sys.executable, str(ROOT / "scripts/verify_model_plans.py"), "--plans", str(plans), "--cohort", "test"],
                         cwd=ROOT, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert run.returncode != 0 and "require model" in run.stderr


def test_advisory_only_labels_do_not_create_a_blocking_escape_denominator():
    from clinverify.eval.harness import evaluate
    rule = catalog.get("R-APP-003")
    result = evaluate([(rule.valid_example, set()), (rule.invalid_example, {rule.id})], catalog, seed=298)
    assert result["n_known_violating"] == 0 and result["n_known_valid"] == 2
    assert result["escape_rate"] == {"rate": None, "ci95": [None, None], "n": 0}
    assert result["false_reject_rate"]["rate"] == 0.0 and result["n_with_advisory_finding"] == 1


def test_blocking_unknown_is_not_counted_as_an_escape():
    from clinverify.eval.harness import evaluate
    from clinverify.plan import Plan
    missing = Plan(case_id=1, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"),
                   postop_antibiotic_days=0, facts={})
    result = evaluate([(missing, {"R-APP-002"})], catalog, seed=298)
    assert result["escape_rate"]["rate"] == 0.0
    assert result["per_rule"]["R-APP-002"]["unknown"] == 1


def test_empty_appendicitis_plan_cannot_earn_checked_acceptance():
    facts = {1: {"pathology": "appendicitis", "facts": {}}}
    result = verify_model_plans([{"case_id": 1, "diagnosis": "appendicitis", "treatments": []}],
                                facts, catalog, expected_case_ids=[1])
    assert result["supported_treatment_validity_rate"] == 1.0  # compatibility diagnostic only
    assert result["supported_checked_acceptance_rate"] == 0.0
    assert result["n_supported_checked_accepted"] == 0
    assert result["n_empty_treatment_plans"] == 1
    assert result["n_supported_accepted_without_decided_blocking_clinical_check"] == 1
    assert result["checked_treatment_status"] == {"accepted_without_decided_blocking_clinical_check": 1}
    assert result["per_case"][0]["n_decided_blocking_clinical_checks"] == 0


def test_advisory_only_or_irrelevant_nonempty_treatment_is_not_checked_success():
    outputs = [{"case_id": 3, "diagnosis": "diverticulitis", "treatments": ["antibiotics"]}]
    result = verify_model_plans(outputs, FACTS, catalog, expected_case_ids=[3])
    assert result["supported_treatment_validity_rate"] == 1.0
    assert result["supported_checked_acceptance_rate"] == 0.0
    assert result["n_empty_treatment_plans"] == 0
    assert result["n_with_advisory_unknown"] == 1


def test_checked_metric_retains_missing_malformed_wrong_and_unknown_cases():
    facts = {**FACTS, 5: {"pathology": "appendicitis", "facts": {}},
             6: {"pathology": "appendicitis", "facts": {"complicated": False}}}
    outputs = [app(), {**app(2), "treatments": ["bad"]},
               {"case_id": 3, "diagnosis": "appendicitis", "treatments": []}, app(5)]
    result = verify_model_plans(outputs, facts, catalog, expected_case_ids=[1, 2, 3, 5, 6])
    assert result["supported_checked_acceptance_rate"] == 1 / 5
    assert result["checked_treatment_status"] == {
        "accepted_with_decided_blocking_clinical_check": 1, "unparseable": 1,
        "wrong_diagnosis": 1, "insufficient_information": 1, "missing_output": 1}
    assert sum(result["checked_treatment_status"].values()) == result["n_supported_cases"]


def test_advisory_violation_does_not_remove_a_decided_blocking_check():
    result = verify_model_plans([app(2, days=7)], FACTS, catalog, expected_case_ids=[2])
    assert result["supported_checked_acceptance_rate"] == 1.0
    assert result["n_with_advisory_finding"] == 1
    assert result["per_case"][0]["n_decided_blocking_clinical_checks"] == 1


def test_unsupported_and_zero_cohorts_never_get_a_checked_score():
    output = {"case_id": 4, "diagnosis": "cholecystitis", "treatments": []}
    result = verify_model_plans([output], FACTS, catalog, expected_case_ids=[4])
    assert result["supported_checked_acceptance_rate"] is None
    assert result["checked_treatment_status"] == {}
    assert result["per_case"][0]["checked_treatment_evaluation_status"] == "unsupported"
    assert verify_model_plans([], {}, catalog, expected_case_ids=[])["supported_checked_acceptance_rate"] is None


def test_automatic_runner_never_fabricates_an_adjudicated_score():
    result = verify_model_plans([app()], FACTS, catalog, expected_case_ids=[1])
    assert result["supported_checked_acceptance_rate"] == 1.0
    assert result["adjudicated_treatment_validity_rate"] is None
    assert result["adjudication_status"] == "unavailable_no_independent_plan_labels_loaded"
    protocol = load_protocol()
    assert protocol["version"] == "1.1"
    assert "supported_treatment_validity_rate_min" not in protocol["targets"]
    assert protocol["targets"]["adjudicated_treatment_validity_rate_min"] == 0.85
    old = json.loads((ROOT / "docs/evaluation_protocol_v1.0.json").read_text())
    assert old["version"] == "1.0" and old["targets"]["supported_treatment_validity_rate_min"] == 0.85
