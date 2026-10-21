"""Starter schema for an LLM-generated discharge / treatment plan, plus the case facts rules may condition on.

This is the structured form the verifier checks (Workbook 1, section 1.4: "fixed schema preferred over free text").
The team should agree the final schema together with the Model A input/output specification.

Plan content comes from the model. `facts` are case facts taken from the patient record (not from the model), such as
whether the appendicitis is complicated. Rules may need either; a missing one makes the rule inconclusive.
Durations are whole days; times (used by the toy rules) are integer hours since admission.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

DIAGNOSES = ("appendicitis", "cholecystitis", "diverticulitis", "pancreatitis")     # pathologies of the benchmark

# Canonical treatment concepts a plan parser must map free text to (a parsing error here is a translation-fidelity error).
TREATMENT_CONCEPTS = ("antibiotics", "preoperative_antibiotic", "appendectomy", "cholecystectomy_during_admission", "ercp",
                      "parenteral_nutrition", "colonoscopy_after_recovery")

# Case facts (booleans) that the current rules use. They must come from the patient record, not from the model.
CASE_FACTS = ("complicated", "low_risk", "infection", "necrotizing", "mild", "biliary", "cholangitis", "biliary_obstruction",
              "oral_or_enteral_feasible", "alarm_symptoms", "crc_screening_up_to_date")


@dataclass(frozen=True)
class Plan:
    case_id: int                                          # hadm_id of the encounter
    diagnosis: str = ""
    treatments: tuple[str, ...] = ()                      # canonical concepts (TREATMENT_CONCEPTS)
    postop_antibiotic_days: Optional[int] = None          # postoperative antibiotic course, in days (0 = none)
    facts: dict[str, bool] = field(default_factory=dict)  # case facts from the record (CASE_FACTS)
    # generic fields used by the toy rules in the tests
    discharge_hour: Optional[int] = None
    medications: tuple[str, ...] = ()
    contraindicated: tuple[str, ...] = ()
    labs: dict[str, Optional[int]] = field(default_factory=dict)
    follow_up: tuple[str, ...] = ()

    def has(self, name: str) -> bool:
        """True if the plan or the case facts state this field. 'facts.<key>' names a case fact.
        None, empty text, empty tuple and empty dict count as not stated; 0 and False count as stated."""
        if name.startswith("facts."):
            return self.facts.get(name[6:]) is not None
        value = getattr(self, name)
        return value is not None and value != "" and value != () and value != {}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        d = dict(d)
        for key in ("treatments", "medications", "contraindicated", "follow_up"):
            d[key] = tuple(d.get(key, ()))
        d["labs"] = dict(d.get("labs", {}))
        d["facts"] = dict(d.get("facts", {}))
        return cls(**d)
