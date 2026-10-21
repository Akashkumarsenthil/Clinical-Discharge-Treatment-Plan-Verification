"""Starter schema for an LLM-generated discharge / treatment plan.

This is the structured form the verifier checks (Workbook 1, section 1.4: "fixed schema preferred over free text").
The fields below are a minimal starting point. The team should agree the final schema together with the Model A
input/output specification and extend it as rules need new inputs.

Times are integer hours since admission, so rules can compare them exactly in Z3.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


# Canonical concept names a plan parser must map free text to (a parsing error here is a translation-fidelity error).
# Taken from the treatment labels in Hager et al. (2024), Fig. 4.
DIAGNOSES = ("appendicitis", "cholecystitis", "diverticulitis", "pancreatitis")
TREATMENT_CONCEPTS = ("antibiotics", "support", "appendectomy", "cholecystectomy", "colectomy", "drainage", "ercp",
                      "future_colonoscopy")


@dataclass(frozen=True)
class Plan:
    case_id: int                                          # hadm_id of the encounter
    diagnosis: str = ""
    discharge_hour: Optional[int] = None                  # planned discharge time; None = not stated
    medications: tuple[str, ...] = ()                     # drugs the plan prescribes
    contraindicated: tuple[str, ...] = ()                 # drugs the record says must be avoided for this patient
    labs: dict[str, Optional[int]] = field(default_factory=dict)   # ordered lab -> hour resulted (None = still pending)
    follow_up: tuple[str, ...] = ()                       # follow-up actions the plan names
    treatments: tuple[str, ...] = ()                      # treatments the plan recommends, as canonical concepts (TREATMENT_CONCEPTS)

    def has(self, name: str) -> bool:
        """True if the plan states this field (None, empty text, empty tuple and empty dict count as not stated)."""
        value = getattr(self, name)
        return value is not None and value != "" and value != () and value != {}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        d = dict(d)
        for key in ("medications", "contraindicated", "follow_up", "treatments"):
            d[key] = tuple(d.get(key, ()))
        d["labs"] = dict(d.get("labs", {}))
        return cls(**d)
