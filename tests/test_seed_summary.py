"""Seed summary combines the three formal runs; synthetic run records only."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.eval.seed_summary import summarize_seed_runs

PROTOCOL = {"generation_seeds": [298, 299, 300]}


def run(seed, acc=0.9, checked=0.2, **over):
    gen = {"model": "m", "model_digest": "d", "prompt_sha256": "0" * 64, "seed": seed, "temperature": 0,
           "top_p": 1, "max_new_tokens": 256}
    gen.update(over)
    return {"diagnosis_accuracy": acc, "supported_checked_acceptance_rate": checked, "supported_treatment_validity_rate": 0.5,
            "validity_rate": 0.4, "joint_success_rate": 0.4, "n_missing_outputs": 0,
            "evaluation": {"cohort": "test", "generation": gen, "cohort_record": {"supported_case_ids_sha256": "x"},
                           "git_commit": "abc", "working_tree_dirty": False}}


def test_mean_and_sd_across_three_seeds():
    out = summarize_seed_runs([run(298, 0.8), run(299, 0.9), run(300, 1.0)], PROTOCOL)
    assert out["seeds"] == [298, 299, 300]
    assert out["mean"]["diagnosis_accuracy"] == pytest.approx(0.9)
    assert out["sd"]["diagnosis_accuracy"] == pytest.approx(0.1)
    assert out["runs"][299]["diagnosis_accuracy"] == 0.9


def test_missing_or_extra_seed_is_refused():
    with pytest.raises(ValueError, match="exactly one run per protocol seed"):
        summarize_seed_runs([run(298), run(299)], PROTOCOL)
    with pytest.raises(ValueError, match="exactly one run per protocol seed"):
        summarize_seed_runs([run(298), run(298), run(299)], PROTOCOL)


def test_runs_that_differ_in_more_than_the_seed_are_refused():
    with pytest.raises(ValueError, match="model_digest"):
        summarize_seed_runs([run(298), run(299), run(300, model_digest="other")], PROTOCOL)
    with pytest.raises(ValueError, match="temperature"):
        summarize_seed_runs([run(298), run(299), run(300, temperature=0.7)], PROTOCOL)


def test_dirty_tree_or_non_test_cohort_is_refused():
    dirty = run(300)
    dirty["evaluation"]["working_tree_dirty"] = True
    with pytest.raises(ValueError, match="clean commit"):
        summarize_seed_runs([run(298), run(299), dirty], PROTOCOL)
    val = run(300)
    val["evaluation"]["cohort"] = "validation"
    with pytest.raises(ValueError, match="test cohort"):
        summarize_seed_runs([run(298), run(299), val], PROTOCOL)


def test_a_null_metric_is_not_averaged_as_zero():
    bad = run(300)
    bad["supported_checked_acceptance_rate"] = None
    out = summarize_seed_runs([run(298), run(299), bad], PROTOCOL)
    assert out["mean"]["supported_checked_acceptance_rate"] is None


def test_zero_sd_is_flagged_as_identical_runs():
    same = summarize_seed_runs([run(298), run(299), run(300)], PROTOCOL)
    assert same["identical_across_seeds"] is True and same["sd"]["diagnosis_accuracy"] == 0
    varied = summarize_seed_runs([run(298, 0.8), run(299, 0.9), run(300, 1.0)], PROTOCOL)
    assert varied["identical_across_seeds"] is False
