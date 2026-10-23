"""Local, aggregate-only catalog feasibility bounds, NOT Model A performance.

Enumerates schema choices with the correct diagnosis and strict record facts.
May include clinically inappropriate or incomplete plans: this is an optimistic
software bound, never a treatment recommendation. No records or IDs are printed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import load_case_facts
from clinverify.eval.protocol import cohort_ids
from clinverify.plan import Plan
from clinverify.rules.catalog import CATALOG_VERSION, COVERED_DIAGNOSES, catalog
from clinverify.verifier.z3_verifier import verify

# Exhaustive for v2.1: other disease-specific tokens do not affect that disease's
# rules. Zero days satisfies both antibiotic-duration constraints whenever known;
# missing or other durations cannot improve the existential acceptance bound.
CONCEPTS = {
    "appendicitis": ("appendectomy", "preoperative_antibiotic"),
    "pancreatitis": ("antibiotics", "cholecystectomy_during_admission", "ercp", "parenteral_nutrition"),
    "diverticulitis": ("antibiotics", "colonoscopy_after_recovery"),
}


def profile_bounds(pathology, facts):
    """Existential software upper bounds for a correct diagnosis, not clinical labels."""
    if CATALOG_VERSION != "2.1":
        raise ValueError("review enumeration assumptions for the new catalog before computing bounds")
    blocking_ids = {r.id for r in catalog if not r.advisory and not r.id.startswith("R-GEN-")}
    any_accepted = any_checked_accepted = False
    unavoidable_unknown = None
    concepts = CONCEPTS[pathology]
    for size in range(len(concepts) + 1):
        for treatments in combinations(concepts, size):
            plan = Plan(0, pathology, treatments, 0 if pathology == "appendicitis" else None, dict(facts))
            result = verify(plan, catalog)
            checked = blocking_ids - set(result.not_applicable) - set(result.inconclusive)
            any_accepted |= result.valid
            any_checked_accepted |= result.valid and bool(checked)
            unknown = set(result.blocking_inconclusive)
            unavoidable_unknown = unknown if unavoidable_unknown is None else unavoidable_unknown & unknown
    return any_accepted, any_checked_accepted, sorted(unavoidable_unknown)


def summarize_bounds(cases, ids, cache=None):
    cache = {} if cache is None else cache
    counts = Counter()
    by_pathology = {}
    unknowns = Counter()
    ids = list(ids)
    if not set(ids) <= set(cases):
        raise ValueError("record facts are missing for a selected cohort case")
    for case_id in ids:
        record = cases[case_id]
        pathology, facts = record["pathology"], record["facts"]
        if pathology not in COVERED_DIAGNOSES:
            continue
        key = pathology, json.dumps(facts, sort_keys=True)
        if key not in cache:
            cache[key] = profile_bounds(pathology, facts)
        accepted, checked, unknown = cache[key]
        row = by_pathology.setdefault(pathology, Counter())
        for target in (counts, row):
            target["covered"] += 1
            target["schema_acceptance_upper_bound_n"] += accepted
            target["checked_acceptance_upper_bound_n"] += checked
            target["unavoidable_blocking_unknown_n"] += bool(unknown)
        unknowns.update(unknown)
    denominator = counts["covered"]
    return {"scheduled": len(ids), "covered": denominator, "unsupported": len(ids) - denominator,
            "schema_acceptance_upper_bound_n": counts["schema_acceptance_upper_bound_n"],
            "schema_acceptance_upper_bound_rate": counts["schema_acceptance_upper_bound_n"] / denominator if denominator else None,
            "checked_acceptance_upper_bound_n": counts["checked_acceptance_upper_bound_n"],
            "checked_acceptance_upper_bound_rate": counts["checked_acceptance_upper_bound_n"] / denominator if denominator else None,
            "unavoidable_blocking_unknown_n": counts["unavoidable_blocking_unknown_n"],
            "unavoidable_unknown_by_rule": dict(unknowns), "by_pathology": by_pathology}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=("validation", "test", "all", "all-groups"), default="validation")
    args = parser.parse_args()
    cases = load_case_facts()  # strict, local only; never print patient text
    groups = ("validation", "test", "all") if args.cohort == "all-groups" else (args.cohort,)
    cache = {}
    result = {"catalog_version": CATALOG_VERSION, "fact_mode": "strict",
              "interpretation": "Optimistic schema bounds with perfect diagnosis; not clinical accuracy, recommended plans, or Model A results.",
              "groups": {group: summarize_bounds(cases, cases if group == "all" else cohort_ids(group), cache)
                         for group in groups}}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
