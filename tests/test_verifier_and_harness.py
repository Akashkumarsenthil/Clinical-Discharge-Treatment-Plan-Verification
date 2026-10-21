"""Verifier, rule interface and harness tests. Synthetic plans and TOY rules only."""
import json
import sys
from pathlib import Path

import pytest
import z3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from clinverify.eval.harness import evaluate  # noqa: E402
from clinverify.plan import Plan  # noqa: E402
from clinverify.rules.base import Rule, RuleCatalog  # noqa: E402
from clinverify.verifier.z3_verifier import verify  # noqa: E402
from tests.toy_rules import catalog  # noqa: E402

GOOD = Plan(case_id=1, diagnosis="dx", discharge_hour=48, medications=("a",), contraindicated=("b",), labs={"x": 10, "y": 40}, follow_up=("clinic",))


def test_valid_plan_passes():
    r = verify(GOOD, catalog)
    assert r.valid and not r.violated and not r.inconclusive


def test_each_violation_is_named():
    late = Plan(case_id=2, diagnosis="dx", discharge_hour=20, medications=("a",), contraindicated=("b",), labs={"x": 30}, follow_up=("clinic",))
    bad_drug = Plan(case_id=3, diagnosis="dx", discharge_hour=48, medications=("b",), contraindicated=("b",), labs={"x": 1}, follow_up=("clinic",))
    no_follow = Plan(case_id=4, diagnosis="dx", discharge_hour=48, medications=("a",), contraindicated=("b",), labs={"x": 1}, follow_up=())
    pending = Plan(case_id=5, diagnosis="dx", discharge_hour=48, medications=("a",), contraindicated=("b",), labs={"x": None}, follow_up=("clinic",))
    assert verify(late, catalog).violated == ("R-TOY-001",)
    assert verify(bad_drug, catalog).violated == ("R-TOY-002",)
    assert verify(no_follow, catalog).inconclusive == ("R-TOY-003",)     # empty follow_up counts as not stated
    assert verify(pending, catalog).violated == ("R-TOY-001",)
    both = Plan(case_id=6, diagnosis="dx", discharge_hour=5, medications=("b",), contraindicated=("b",), labs={"x": 9}, follow_up=("clinic",))
    assert set(verify(both, catalog).violated) == {"R-TOY-001", "R-TOY-002"}


def test_missing_input_is_inconclusive_not_valid():
    r = verify(Plan(case_id=7, diagnosis="dx", discharge_hour=None, medications=("a",), contraindicated=("b",), labs={"x": 1}, follow_up=("c",)), catalog)
    assert r.inconclusive == ("R-TOY-001",) and not r.valid and not r.complete


def test_rule_registration_enforces_id_source_and_uniqueness():
    c = RuleCatalog()
    f = lambda plan: z3.BoolVal(True)  # noqa: E731
    with pytest.raises(ValueError):
        c.add(Rule("bad id", "d", "s", (), f))
    with pytest.raises(ValueError):
        c.add(Rule("R-AAA-001", "d", "", (), f))             # no source
    with pytest.raises(ValueError):
        c.add(Rule("R-AAA-001", "d", "s", ("not_a_field",), f))
    c.add(Rule("R-AAA-001", "d", "s", (), f))
    with pytest.raises(ValueError):
        c.add(Rule("R-AAA-001", "d", "s", (), f))            # duplicate


def labeled():
    return [(GOOD, set()),
            (Plan(case_id=2, diagnosis="dx", discharge_hour=20, medications=("a",), contraindicated=("b",), labs={"x": 30}, follow_up=("clinic",)), {"R-TOY-001"}),
            (Plan(case_id=3, diagnosis="dx", discharge_hour=48, medications=("b",), contraindicated=("b",), labs={"x": 1}, follow_up=("clinic",)), {"R-TOY-002"})]


def test_harness_metrics_with_full_and_partial_rule_sets():
    full = evaluate(labeled(), catalog, seed=1)
    assert full["escape_rate"]["rate"] == 0.0 and full["false_reject_rate"]["rate"] == 0.0
    assert full["exact_rule_match"]["rate"] == 1.0 and full["n_plans"] == 3
    partial = evaluate(labeled(), [r for r in catalog if r.id == "R-TOY-001"], seed=1)   # verifier lacks the drug rule
    assert partial["escape_rate"]["rate"] == 0.5          # the drug violation escapes


def test_harness_is_reproducible_for_a_seed():
    a, b = evaluate(labeled(), catalog, seed=7), evaluate(labeled(), catalog, seed=7)
    a.pop("solver_ms"); b.pop("solver_ms")
    assert a == b


def test_plan_roundtrip_and_toy_file():
    assert Plan.from_dict(GOOD.to_dict()) == GOOD
    items = json.loads((ROOT / "tests" / "data" / "toy_labeled_plans.json").read_text())
    pairs = [(Plan.from_dict(i["plan"]), set(i["violates"])) for i in items]
    assert evaluate(pairs, catalog, seed=1)["exact_rule_match"]["rate"] == 1.0
