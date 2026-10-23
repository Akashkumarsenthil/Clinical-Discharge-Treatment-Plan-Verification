"""Model plans + record facts -> verifier, on synthetic case facts (no dataset needed)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import plan_from_model_output  # noqa: E402
from clinverify.eval.model_run import verify_model_plans  # noqa: E402
from clinverify.rules.catalog import catalog  # noqa: E402

FACTS = {
    1: {"pathology": "appendicitis", "facts": {"complicated": False}},
    2: {"pathology": "pancreatitis", "facts": {"infection": False, "necrotizing": False, "mild": True, "biliary": True}},
    3: {"pathology": "diverticulitis", "facts": {"complicated": False, "alarm_symptoms": False}},
}


def test_facts_come_from_the_record_and_model_facts_are_rejected():
    plan = plan_from_model_output({"case_id": 1, "diagnosis": "appendicitis", "treatments": ["appendectomy"]}, FACTS)
    assert plan.facts == {"complicated": False}
    with pytest.raises(ValueError, match="unknown fields"):
        plan_from_model_output({"case_id": 1, "diagnosis": "appendicitis", "facts": {"complicated": True}}, FACTS)


@pytest.mark.parametrize("bad", [
    {"diagnosis": "appendicitis"},                                                   # no case_id
    {"case_id": 99, "diagnosis": "appendicitis"},                                    # unknown case
    {"case_id": 1, "diagnosis": "gout"},                                             # unknown diagnosis
    {"case_id": 1, "diagnosis": "appendicitis", "treatments": ["magic"]},            # unknown concept
    {"case_id": 1, "diagnosis": "appendicitis", "postop_antibiotic_days": -1},       # bad days
])
def test_unparseable_output_is_rejected(bad):
    with pytest.raises(ValueError):
        plan_from_model_output(bad, FACTS)


def test_end_to_end_valid_violated_and_insufficient():
    outputs = [
        {"case_id": 1, "diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"],
         "postop_antibiotic_days": 0},                                              # valid
        {"case_id": 2, "diagnosis": "pancreatitis", "treatments": ["antibiotics", "cholecystectomy_during_admission"]},  # R-PAN-001
        {"case_id": 3, "diagnosis": "diverticulitis", "treatments": []},            # insufficient (colonoscopy rule needs facts it lacks)
        {"case_id": 1, "diagnosis": "gout"},                                        # unparseable
    ]
    s = verify_model_plans(outputs, FACTS, catalog)
    assert s["n_plans"] == 4 and s["n_unparseable"] == 1
    by_case = {c["case_id"]: c for c in s["per_case"]}
    assert by_case[1]["status"] == "valid"
    assert by_case[2]["status"] == "violated" and "R-PAN-001" in by_case[2]["violated"]
    assert by_case[3]["status"] == "insufficient_information"
    assert s["violations_by_rule"] == {"R-PAN-001": 1}
    assert s["validity_rate"] == 0.25


def test_wrong_diagnosis_is_counted():
    s = verify_model_plans([{"case_id": 1, "diagnosis": "pancreatitis", "treatments": []}], FACTS, catalog)
    assert s["n_wrong_diagnosis"] == 1
