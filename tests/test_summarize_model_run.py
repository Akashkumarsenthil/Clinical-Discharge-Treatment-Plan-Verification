"""Evaluation summary for a generated run; invented IDs and synthetic facts only."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("summarize_model_run", ROOT / "scripts/summarize_model_run.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)

REF = {1: "appendicitis", 2: "appendicitis", 3: "cholecystitis", 4: "pancreatitis", 5: "diverticulitis"}


def test_missing_prediction_counts_as_wrong_and_costs_recall():
    m = S.diagnosis_metrics({1: "appendicitis", 2: "appendicitis", 3: "cholecystitis", 4: "pancreatitis"}, REF)
    assert m["n"] == 5 and m["n_missing"] == 1 and m["accuracy"] == pytest.approx(0.8)
    assert m["per_pathology"]["diverticulitis"] == {"n": 1, "recall": 0.0}
    # diverticulitis F1 = 0, the other three = 1
    assert m["macro_f1"] == pytest.approx(0.75)


def test_off_list_answer_is_wrong_not_a_new_class():
    m = S.diagnosis_metrics({1: "gastritis", 2: "appendicitis", 3: "cholecystitis", 4: "pancreatitis",
                             5: "diverticulitis"}, REF)
    assert m["accuracy"] == pytest.approx(0.8) and m["n_missing"] == 0
    assert m["per_pathology"]["appendicitis"]["recall"] == pytest.approx(0.5)


def test_empty_reference():
    assert S.diagnosis_metrics({}, {})["accuracy"] is None


def _verify_run(path, **extra):
    path.write_text(json.dumps({"scoring_population": "fixed_cohort", "per_case": [], "n_plans": 5,
                                "supported_checked_acceptance_rate": 0.25, "joint_success_rate": 0.2,
                                "status": {"valid": 1}, **extra}))


def test_latest_verify_run_ignores_run_eval_logs(tmp_path):
    _verify_run(tmp_path / "run_20261115T010000000000.json", n_plans=5)
    (tmp_path / "run_20261115T020000_catalog_labeled_plans_seed298.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "run_broken.json").write_text("{not json")
    path, data = S.latest_verify_run(tmp_path)
    assert path.name == "run_20261115T010000000000.json" and data["n_plans"] == 5
    with pytest.raises(FileNotFoundError):
        S.latest_verify_run(tmp_path / "empty")


def test_out_of_cohort_plan_is_refused():
    with pytest.raises(ValueError, match="outside"):
        S.summarize([{"case_id": 99, "diagnosis": "appendicitis"}], REF, {}, None, "validation")


def test_pilot_scores_submitted_cases_only():
    s = S.summarize([{"case_id": 1, "diagnosis": "Appendicitis "}], REF, {"n_plans": 1}, None, "pilot")
    assert s["diagnosis"]["n"] == 1 and s["diagnosis"]["accuracy"] == 1.0


def test_cli_writes_aggregate_summary_without_text(tmp_path):
    plans = tmp_path / "model_a_x_val_seed298.json"
    plans.write_text(json.dumps([{"case_id": h, "diagnosis": d, "treatments": ["antibiotics"]} for h, d in REF.items()]))
    plans.with_suffix(".metadata.json").write_text(json.dumps({"model": "synthetic", "seed": 298}))
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({str(h): {"pathology": d, "facts": {}} for h, d in REF.items()}))
    split = tmp_path / "split.json"
    split.write_text(json.dumps({"splits": {"val": list(REF), "test": []}}))
    _verify_run(tmp_path / "run_20261115T010000000000.json")
    assert S.main(["--plans", str(plans), "--verify-dir", str(tmp_path), "--facts-json", str(facts),
                   "--split-file", str(split)]) == 0
    out = json.loads((tmp_path / "evaluation_summary.json").read_text())
    assert out["diagnosis"]["accuracy"] == 1.0 and out["diagnosis"]["macro_f1"] == 1.0
    assert out["plans"]["supported_checked_acceptance_rate"] == 0.25
    assert out["generation"] == {"model": "synthetic", "seed": 298}
    assert "antibiotics" not in json.dumps(out)
