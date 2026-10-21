"""The draft rule catalog: one valid and one violating synthetic plan per rule, plus structure checks."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.eval.harness import evaluate  # noqa: E402
from clinverify.plan import DIAGNOSES, TREATMENT_CONCEPTS, Plan  # noqa: E402
from clinverify.rules.catalog import ESSENTIAL_TREATMENTS, catalog  # noqa: E402
from clinverify.verifier.z3_verifier import verify  # noqa: E402

FULL = {"appendicitis": ("antibiotics", "support", "appendectomy"), "cholecystitis": ("antibiotics", "support", "cholecystectomy"),
        "diverticulitis": ("antibiotics", "support", "future_colonoscopy", "colectomy"), "pancreatitis": ("support", "ercp")}


def test_every_rule_has_a_source_a_known_diagnosis_and_a_known_treatment():
    assert len(catalog) == len(ESSENTIAL_TREATMENTS) == 8
    for rule in catalog:
        assert "Hager" in rule.source and "guideline" in rule.source
    for _, diagnosis, treatment in ESSENTIAL_TREATMENTS:
        assert diagnosis in DIAGNOSES and treatment in TREATMENT_CONCEPTS


@pytest.mark.parametrize("rule_id,diagnosis,treatment", ESSENTIAL_TREATMENTS)
def test_each_rule_passes_a_compliant_plan_and_flags_the_missing_treatment(rule_id, diagnosis, treatment):
    good = Plan(1, diagnosis, treatments=FULL[diagnosis])
    assert verify(good, catalog).valid
    missing = tuple(t for t in FULL[diagnosis] if t != treatment)
    result = verify(Plan(2, diagnosis, treatments=missing), catalog)
    assert rule_id in result.violated and not result.valid


def test_rules_only_apply_to_their_own_diagnosis():
    assert verify(Plan(3, "pancreatitis", treatments=("support",)), catalog).valid          # no antibiotics needed here
    assert verify(Plan(4, "appendicitis", treatments=("antibiotics", "support")), catalog).valid   # no colonoscopy needed here


def test_plan_that_recommends_nothing_is_a_violation_not_inconclusive():
    r = verify(Plan(5, "diverticulitis"), catalog)
    assert set(r.violated) == {"R-TRT-005", "R-TRT-006", "R-FUP-001"} and not r.inconclusive


def test_plan_without_a_diagnosis_is_inconclusive():
    r = verify(Plan(6, "", treatments=("support",)), catalog)
    assert len(r.inconclusive) == 8 and not r.violated and not r.valid


def test_labeled_synthetic_plans_are_scored_exactly():
    items = json.loads((ROOT / "tests" / "data" / "catalog_labeled_plans.json").read_text())
    pairs = [(Plan.from_dict(i["plan"]), set(i["violates"])) for i in items]
    m = evaluate(pairs, catalog, seed=298)
    assert m["escape_rate"]["rate"] == 0.0 and m["false_reject_rate"]["rate"] == 0.0 and m["exact_rule_match"]["rate"] == 1.0
