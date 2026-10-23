"""Attach real case facts to a model's plan so the verifier can run on benchmark cases.

The model only supplies plan content (diagnosis, treatments, antibiotic days). Case facts always come from the
patient record via `derive_facts`; a fact the model sends is rejected, never used.
"""
from __future__ import annotations

from typing import Iterable, Optional

from clinverify.data.case_facts import derive_facts
from clinverify.plan import DIAGNOSES, TREATMENT_CONCEPTS, Plan

# the only fields Model A may output (see docs/model_a_plan_format.md)
MODEL_PLAN_FIELDS = ("case_id", "diagnosis", "treatments", "postop_antibiotic_days")


def load_case_facts(hadm_ids: Optional[Iterable[int]] = None) -> dict[int, dict]:
    """{hadm_id: {"pathology": str, "facts": {...}}} from the Ext-CDM data in MIMIC_DIR. Reads local data only."""
    from clinverify.data import ext_cdm as E

    ids = E.load_pathology_ids()
    pathology_of = {h: p for p, hs in ids.items() for h in hs}
    titles = E.load_tables()["icd_diagnosis"].groupby("hadm_id")["icd_diagnosis"].apply(list).to_dict()
    wanted = set(pathology_of) if hadm_ids is None else {int(h) for h in hadm_ids}
    return {h: {"pathology": pathology_of[h], "facts": derive_facts(pathology_of[h], titles.get(h, []))}
            for h in wanted if h in pathology_of}


def plan_from_model_output(output: dict, case_facts: dict[int, dict]) -> Plan:
    """Build a Plan from Model A's output and the record's facts. Raises ValueError for output that cannot be parsed."""
    extra = set(output) - set(MODEL_PLAN_FIELDS)
    if extra:
        raise ValueError(f"unknown fields {sorted(extra)}; allowed: {list(MODEL_PLAN_FIELDS)} (case facts come from the record)")
    if "case_id" not in output:
        raise ValueError("missing case_id")
    case_id = int(output["case_id"])
    if case_id not in case_facts:
        raise ValueError(f"case_id {case_id} is not a known benchmark case")
    diagnosis = output.get("diagnosis", "")
    if diagnosis not in DIAGNOSES:
        raise ValueError(f"diagnosis {diagnosis!r} is not one of {list(DIAGNOSES)}")
    treatments = tuple(output.get("treatments", ()))
    unknown = [t for t in treatments if t not in TREATMENT_CONCEPTS]
    if unknown:
        raise ValueError(f"unknown treatment concepts {unknown}; allowed: {list(TREATMENT_CONCEPTS)}")
    days = output.get("postop_antibiotic_days")
    if days is not None and (not isinstance(days, int) or isinstance(days, bool) or days < 0):
        raise ValueError("postop_antibiotic_days must be a whole number of days >= 0, or null if not stated")
    return Plan(case_id=case_id, diagnosis=diagnosis, treatments=treatments, postop_antibiotic_days=days,
                facts=dict(case_facts[case_id]["facts"]))
