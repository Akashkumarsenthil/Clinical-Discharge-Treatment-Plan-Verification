"""Feasibility enumeration uses synthetic facts only, not patient data."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("feasibility", ROOT / "scripts/check_evaluation_feasibility.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unknown_appendicitis_only_passes_without_a_meaningful_check():
    accepted, checked, unavoidable = module.profile_bounds("appendicitis", {})
    assert accepted and not checked and unavoidable == []  # surgery is optional in the catalog


def test_unknown_pancreatitis_and_diverticulitis_block_every_schema_plan():
    accepted, checked, unavoidable = module.profile_bounds("pancreatitis", {})
    assert not accepted and not checked
    assert set(unavoidable) == {"R-PAN-002", "R-PAN-003"}
    accepted, checked, unavoidable = module.profile_bounds("diverticulitis", {})
    assert not accepted and not checked and unavoidable == ["R-DIV-002"]


def test_known_complicated_diverticulitis_has_a_checked_plan():
    accepted, checked, unavoidable = module.profile_bounds("diverticulitis", {"complicated": True})
    assert accepted and checked and not unavoidable


def test_summary_preserves_full_scope_and_aggregates_only():
    cases = {1: {"pathology": "appendicitis", "facts": {}},
             2: {"pathology": "diverticulitis", "facts": {"complicated": True}},
             3: {"pathology": "pancreatitis", "facts": {}},
             4: {"pathology": "cholecystitis", "facts": {}}}
    result = module.summarize_bounds(cases, cases)
    assert result["scheduled"] == 4 and result["covered"] == 3 and result["unsupported"] == 1
    assert result["schema_acceptance_upper_bound_n"] == 2
    assert result["checked_acceptance_upper_bound_n"] == 1
    assert result["schema_acceptance_upper_bound_rate"] == 2 / 3
    assert result["checked_acceptance_upper_bound_rate"] == 1 / 3
    with pytest.raises(ValueError, match="record facts"):
        module.summarize_bounds(cases, [99])
