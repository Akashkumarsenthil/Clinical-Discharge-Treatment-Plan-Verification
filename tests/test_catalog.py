"""Rule catalog v2.1: every rule is documented, sourced, and verified on its own valid and invalid example."""
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
    assert [r.id for r in RULES] == ["R-GEN-001", "R-APP-001", "R-APP-002", "R-APP-003", "R-PAN-001", "R-PAN-002", "R-PAN-003",
                                     "R-PAN-004", "R-PAN-005", "R-DIV-001", "R-DIV-002", "R-DIV-003"]
    assert catalog.undocumented() == []


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_each_rule_cites_a_numbered_statement_or_section_and_a_strength(rule):
    assert any(token in rule.source for token in ("2025", "2026", "Project scope")), rule.source
    assert any(token in rule.source for token in ("full text", "abstract only", "Project scope"))      # says what was read
    assert rule.source_date in ("2025", "2026"), "the course asks for sources no older than 3-4 years"
    assert rule.strength and rule.violation_message and rule.recommendation


@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_valid_example_passes_the_whole_catalog_and_invalid_example_breaks_only_this_rule(rule):
    ok = verify(rule.valid_example, catalog)
    assert ok.valid and ok.status == "valid", ok
    bad = verify(rule.invalid_example, catalog)
    assert bad.violated == (rule.id,) and not bad.inconclusive, bad
    assert bad.messages[rule.id] == ("(advisory) " if rule.advisory else "") + rule.violation_message
    assert (rule.id in bad.advisory) == rule.advisory
    if rule.advisory:      # a suggestion: reported, but the plan is not invalid
        assert bad.valid and bad.status == "valid" and bad.blocking == ()
    else:
        assert not bad.valid and bad.status == "violated" and bad.blocking == (rule.id,)


def test_rules_only_use_known_fields_facts_treatments_and_diagnoses():
    from clinverify.rules.catalog import COVERED_DIAGNOSES
    assert set(COVERED_DIAGNOSES) <= set(DIAGNOSES)
    for rule in RULES:
        for name in rule.requires:
            assert name.startswith("facts.") is False or name[6:] in CASE_FACTS, (rule.id, name)
        for plan in (rule.valid_example, rule.invalid_example):
            assert set(plan.treatments) <= set(TREATMENT_CONCEPTS) and set(plan.facts) <= set(CASE_FACTS)
            assert plan.diagnosis in DIAGNOSES


def test_missing_information_never_passes():
    no_diagnosis = verify(Plan(case_id=1, treatments=("antibiotics",)), catalog)
    assert no_diagnosis.status == "insufficient_information" and not no_diagnosis.valid
    appendectomy_without_facts = Plan(case_id=2, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"))
    r = verify(appendectomy_without_facts, catalog)
    assert set(r.inconclusive) == {"R-APP-002", "R-APP-003"} and not r.valid


def test_unsupported_diagnosis_is_flagged_not_silently_valid():
    r = verify(Plan(case_id=3, diagnosis="cholecystitis", treatments=("antibiotics",)), catalog)
    assert r.violated == ("R-GEN-001",) and not r.valid


def test_advisory_rules_are_reported_separately():
    r = verify(_div_plan(antibiotics=True), catalog)
    assert r.violated == ("R-DIV-001",) and r.advisory == ("R-DIV-001",) and r.blocking == ()
    blocking = verify(next(x.invalid_example for x in RULES if x.id == "R-PAN-001"), catalog)
    assert blocking.blocking == ("R-PAN-001",) and blocking.advisory == ()


def _div_plan(antibiotics):
    return next(x.valid_example for x in RULES if x.id == "R-DIV-001") if not antibiotics else \
        next(x.invalid_example for x in RULES if x.id == "R-DIV-001")


def test_a_stated_zero_is_information_but_an_unstated_value_is_not():
    p = Plan(case_id=4, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"), postop_antibiotic_days=0,
             facts=dict(complicated=False))
    assert verify(p, catalog).valid
    from dataclasses import replace
    assert "R-APP-002" in verify(replace(p, postop_antibiotic_days=None), catalog).inconclusive


def test_rules_do_not_apply_to_other_diagnoses():
    r = verify(next(rule.valid_example for rule in RULES if rule.id == "R-DIV-002"), catalog)
    assert r.valid and "R-APP-001" in r.not_applicable and "R-PAN-001" in r.not_applicable


def test_labeled_synthetic_plans_file_is_current_and_scored_exactly():
    items = json.loads((ROOT / "tests" / "data" / "catalog_labeled_plans.json").read_text())
    assert items == json.loads(json.dumps(labeled_plans()))
    pairs = [(Plan.from_dict(i["plan"]), set(i["violates"])) for i in items]
    m = evaluate(pairs, catalog, seed=298)
    assert m["escape_rate"]["rate"] == 0.0 and m["false_reject_rate"]["rate"] == 0.0 and m["exact_rule_match"]["rate"] == 1.0
    assert m["n_plans"] == len(items) == 29


def test_rule_catalog_doc_is_generated_from_the_code():
    from build_rule_catalog_doc import build
    assert (ROOT / "docs" / "rule_catalog.md").read_text() == build()


def test_signoff_page_lists_every_rule():
    page = (ROOT / "docs" / "rule_signoff.md").read_text()
    for rule in RULES:
        assert f"`{rule.id}`" in page, f"{rule.id} is missing from docs/rule_signoff.md"


def test_advisory_violation_is_reported_but_does_not_make_the_plan_invalid():
    r = verify(next(x.invalid_example for x in RULES if x.id == "R-DIV-001"), catalog)
    assert r.violated == ("R-DIV-001",) and r.advisory == ("R-DIV-001",) and r.valid and r.status == "valid"


def test_a_rule_whose_condition_fact_is_false_is_not_applicable_instead_of_passing():
    plan = Plan(case_id=1, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"),
                postop_antibiotic_days=0, facts={"complicated": False})
    r = verify(plan, catalog)
    assert "R-APP-003" in r.not_applicable and "R-APP-002" not in r.not_applicable
    plan2 = Plan(case_id=2, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"),
                 postop_antibiotic_days=5, facts={"complicated": True})
    assert "R-APP-002" in verify(plan2, catalog).not_applicable


def test_postoperative_course_rule_needs_an_appendectomy_and_only_checks_the_upper_bound():
    no_surgery = Plan(case_id=3, diagnosis="appendicitis", treatments=("antibiotics",), postop_antibiotic_days=7,
                      facts={"complicated": True})
    assert "R-APP-003" in verify(no_surgery, catalog).not_applicable
    zero_days = Plan(case_id=4, diagnosis="appendicitis", treatments=("appendectomy", "preoperative_antibiotic"),
                     postop_antibiotic_days=0, facts={"complicated": True})
    r = verify(zero_days, catalog)
    assert "R-APP-003" not in r.violated and "R-APP-003" not in r.inconclusive        # passes: it is only an upper bound


def test_known_alarm_symptoms_decide_the_colonoscopy_rule_without_screening_history():
    plan = Plan(case_id=5, diagnosis="diverticulitis", treatments=(), facts={"complicated": False, "alarm_symptoms": True})
    r = verify(plan, catalog)
    assert "R-DIV-003" in r.violated and "R-DIV-003" not in r.inconclusive
    unknown = Plan(case_id=6, diagnosis="diverticulitis", treatments=(), facts={"complicated": False})
    assert "R-DIV-003" in verify(unknown, catalog).inconclusive


def test_per_rule_counts_cover_every_rule_and_sum_to_the_number_of_plans():
    from clinverify.eval.harness import evaluate
    plans = [(rule.valid_example, set()) for rule in RULES] + [(rule.invalid_example, {rule.id}) for rule in RULES]
    m = evaluate(plans, catalog, 298)
    assert set(m["per_rule"]) == {r.id for r in RULES}
    assert all(sum(row.values()) == len(plans) for row in m["per_rule"].values())
