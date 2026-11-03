"""Combine the three formal generation runs (seeds 298, 299, 300) into one report: each run plus mean and standard deviation.

The protocol (docs/metrics.md) treats the seeds as repeated generations of the same frozen model on the same cases, not as
independent patients. This refuses to combine runs that differ in anything but the seed.
"""
from __future__ import annotations

from statistics import mean, stdev

METRICS = ("diagnosis_accuracy", "supported_checked_acceptance_rate", "supported_treatment_validity_rate",
           "validity_rate", "joint_success_rate", "n_missing_outputs")
SAME_ACROSS_SEEDS = ("model", "model_digest", "prompt_sha256", "temperature", "top_p", "max_new_tokens")


def summarize_seed_runs(runs: list[dict], protocol: dict) -> dict:
    """runs: result files written by scripts/verify_model_plans.py --cohort test (one per seed)."""
    seeds = [r["evaluation"]["generation"]["seed"] for r in runs]
    if sorted(seeds) != sorted(protocol["generation_seeds"]):
        raise ValueError(f"need exactly one run per protocol seed {protocol['generation_seeds']}, got {sorted(seeds)}")
    for key in SAME_ACROSS_SEEDS:
        if len({r["evaluation"]["generation"][key] for r in runs}) != 1:
            raise ValueError(f"runs differ in {key}; only the seed may change")
    if any(r["evaluation"]["cohort"] != "test" for r in runs):
        raise ValueError("every run must be on the test cohort")
    if len({r["evaluation"]["cohort_record"]["supported_case_ids_sha256"] for r in runs}) != 1:
        raise ValueError("runs use different covered-case selections")
    if len({r["evaluation"]["git_commit"] for r in runs}) != 1 or any(r["evaluation"]["working_tree_dirty"] for r in runs):
        raise ValueError("runs must come from one clean commit")
    ordered = sorted(runs, key=lambda r: r["evaluation"]["generation"]["seed"])
    out = {"seeds": sorted(seeds), "runs": {}, "mean": {}, "sd": {}}
    for r in ordered:
        out["runs"][r["evaluation"]["generation"]["seed"]] = {m: r.get(m) for m in METRICS}
    for m in METRICS:
        values = [r.get(m) for r in ordered]
        if any(v is None for v in values):          # a null stays null; it is never averaged as zero
            out["mean"][m] = out["sd"][m] = None
        else:
            out["mean"][m], out["sd"][m] = mean(values), stdev(values)
    return out
