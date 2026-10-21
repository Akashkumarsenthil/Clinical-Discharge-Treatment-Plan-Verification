"""Rule catalog v1.0: every rule is documented, sourced, and verified on its own valid and invalid example."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from clinverify.eval.harness import evaluate  # noqa: E402
from clinverify.plan import CASE_FACTS, DIAGNOSES, TREATMENT_CONCEPTS, Plan  # noqa: E402
from clinverify.rules.catalog import catalog  # noqa: E402
from clinverify.verifier.z3_verifier import verify  # noqa: E402
from make_catalog_labeled_plans import labeled_plans  # noqa: E402

RULES = list(catalog)


def test_catalog_has_the_expected_rules_and_every_rule_is_fully_documented():
    assert [r.id for r in RULES] == ["R-GEN-001", "R-APP-001", "R-APP-002", "R-APP-003", "R-APP-004", "R-CHO-001", "R-CHO-002",
                                     "R-PAN-001", "R-PAN-002", "R-PAN-003", "R-PAN-004", "R-PAN-005", "R-DIV-001", "R-DIV-002"]
    assert catalog.undocumented() == []


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_each_rule_cites_a_numbered_statement_or_section_and_a_strength(rule):
    assert "WSES" in rule.source or "Project scope" in rule.source
    assert any(token in rule.source for token in ("Recommendation", "section", "statement", "Project scope"))
    assert rule.strength and rule.violation_message and rule.recommendation


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_valid_example_passes_the_whole_catalog_and_invalid_example_breaks_only_this_rule(rule):
    ok = verify(rule.valid_example, catalog)
    assert ok.valid and ok.status == "valid", ok
    bad = verify(rule.invalid_example, catalog)
    assert bad.violated == (rule.id,) and not bad.inconclusive and bad.status == "violated", bad
    assert bad.messages[rule.id] == rule.violation_message


def test_rules_only_use_known_fields_facts_treatments_and_diagnoses():
    for rule in RULES:
        for name in rule.requires:
            assert name.startswith("facts.") is False or name[6:] in CASE_FACTS, (rule.id, name)
        for plan in (rule.valid_example, rule.invalid_example):
            assert set(plan.treatments) <= set(TREATMENT_CONCEPTS) and set(plan.facts) <= set(CASE_FACTS)
            assert plan.diagnosis in DIAGNOSES or plan.diagnosis == "migraine"


def test_missing_information_never_passes():
    no_diagnosis = verify(Plan(case_id=1, treatments=("antibiotics",)), catalog)
    assert no_diagnosis.status == "insufficient_information" and not no_diagnosis.valid
    appendectomy_without_facts = Plan(case_id=2, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"))
    r = verify(appendectomy_without_facts, catalog)
    assert set(r.inconclusive) == {"R-APP-002", "R-APP-003", "R-APP-004"} and not r.valid
    cholecystitis_without_facts = verify(Plan(case_id=3, diagnosis="cholecystitis", treatments=("cholecystectomy",)), catalog)
    assert "R-CHO-002" in cholecystitis_without_facts.inconclusive


def test_a_stated_zero_is_information_but_an_unstated_value_is_not():
    p = Plan(case_id=4, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"), postop_antibiotic_days=0,
             appendectomy_hour=12, facts=dict(complicated=False, source_control_adequate=True, adult=True))
    assert verify(p, catalog).valid
    from dataclasses import replace
    assert "R-APP-002" in verify(replace(p, postop_antibiotic_days=None), catalog).inconclusive


def test_rules_do_not_apply_to_other_diagnoses():
    r = verify(_cholecystitis_ok(), catalog)
    assert r.valid and "R-APP-001" in r.not_applicable and "R-PAN-001" in r.not_applicable


def _cholecystitis_ok():
    return next(rule.valid_example for rule in RULES if rule.id == "R-CHO-001")


def test_labeled_synthetic_plans_file_is_current_and_scored_exactly():
    items = json.loads((ROOT / "tests" / "data" / "catalog_labeled_plans.json").read_text())
    assert items == json.loads(json.dumps(labeled_plans()))
    pairs = [(Plan.from_dict(i["plan"]), set(i["violates"])) for i in items]
    m = evaluate(pairs, catalog, seed=298)
    assert m["escape_rate"]["rate"] == 0.0 and m["false_reject_rate"]["rate"] == 0.0 and m["exact_rule_match"]["rate"] == 1.0
    assert m["n_plans"] == len(items) == 32


def test_rule_catalog_doc_is_generated_from_the_code():
    from build_rule_catalog_doc import build
    assert (ROOT / "docs" / "rule_catalog.md").read_text() == build()
