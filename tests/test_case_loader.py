"""Model plans + record facts -> verifier, on synthetic case facts (no dataset needed)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import case_facts_from_tables, plan_from_model_output  # noqa: E402
from clinverify.eval.model_run import verify_model_plans  # noqa: E402
from clinverify.rules.catalog import catalog  # noqa: E402

FACTS = {
    1: {"pathology": "appendicitis", "facts": {"complicated": False}},
    2: {"pathology": "pancreatitis", "facts": {"infection": False, "necrotizing": False, "mild": True, "biliary": True}},
    3: {"pathology": "diverticulitis", "facts": {"complicated": False, "alarm_symptoms": False}},
    4: {"pathology": "appendicitis", "facts": {}},                      # complication status unknown
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
        {"case_id": 3, "diagnosis": "diverticulitis", "treatments": []},            # valid; the advisory colonoscopy rule lacks screening history
        {"case_id": 4, "diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"],
         "postop_antibiotic_days": 0},                                              # insufficient: complication status unknown
        {"case_id": 1, "diagnosis": "gout"},                                        # unparseable
    ]
    s = verify_model_plans(outputs, FACTS, catalog)
    assert s["n_plans"] == 5 and s["n_unparseable"] == 1
    by_case = {c["case_id"]: c for c in s["per_case"]}
    assert by_case[1]["status"] == "valid"
    assert by_case[2]["status"] == "violated" and "R-PAN-001" in by_case[2]["violated"]
    assert by_case[3]["status"] == "valid" and by_case[3]["advisory_inconclusive"] == ["R-DIV-003"]
    assert by_case[4]["status"] == "insufficient_information" and "R-APP-002" in by_case[4]["inconclusive"]
    assert s["violations_by_rule"] == {"R-PAN-001": 1}
    assert s["validity_rate"] == 0.4                                                # 2 of 5 plans
    assert set(s["per_rule"]) == {r.id for r in catalog}


def test_wrong_diagnosis_is_counted():
    s = verify_model_plans([{"case_id": 1, "diagnosis": "pancreatitis", "treatments": []}], FACTS, catalog)
    assert s["n_wrong_diagnosis"] == 1


def test_loader_uses_icd_titles_and_the_discharge_text_through_one_path():
    import pandas as pd
    icd = pd.DataFrame({"hadm_id": [1, 1, 2], "icd_diagnosis": ["Unspecified acute appendicitis", "Hypertension",
                                                                 "Unspecified acute appendicitis"]})
    discharge = pd.DataFrame({"hadm_id": [1, 2], "discharge_diagnosis": ["Perforated appendicitis", "Appendicitis"]})
    facts = case_facts_from_tables({1: "appendicitis", 2: "appendicitis"}, icd, discharge)
    assert facts[1]["facts"] == {"complicated": True}            # added by the discharge text
    assert facts[2]["facts"] == {}                               # nothing written: unknown
    only_one = case_facts_from_tables({1: "appendicitis", 2: "appendicitis"}, icd, discharge, hadm_ids=[2])
    assert list(only_one) == [2]


def test_sensitivity_mode_is_separate_from_the_strict_loader_output():
    import pandas as pd
    icd = pd.DataFrame({"hadm_id": [5], "icd_diagnosis": ["Idiopathic acute pancreatitis without necrosis or infection"]})
    discharge = pd.DataFrame({"hadm_id": [5], "discharge_diagnosis": ["Acute pancreatitis"]})
    strict = case_facts_from_tables({5: "pancreatitis"}, icd, discharge)[5]["facts"]
    sens = case_facts_from_tables({5: "pancreatitis"}, icd, discharge, sensitivity=True)[5]["facts"]
    assert "cholangitis" not in strict and sens["cholangitis"] is False


def test_diagnosis_correctness_is_reported_separately_from_treatment_validity():
    outputs = [
        {"case_id": 1, "diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"], "postop_antibiotic_days": 0},
        {"case_id": 1, "diagnosis": "pancreatitis", "treatments": []},                 # wrong diagnosis for case 1
    ]
    s = verify_model_plans(outputs, FACTS, catalog)
    assert s["n_wrong_diagnosis"] == 1 and s["diagnosis_accuracy"] == 0.5
    assert s["validity_rate_diagnosis_correct"] == 1.0                                 # scored on the correct-diagnosis plan only
    assert [c["diagnosis_correct"] for c in s["per_case"]] == [True, False]
