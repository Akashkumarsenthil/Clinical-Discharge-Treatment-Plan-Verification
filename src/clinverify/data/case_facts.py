"""Derive the case facts that the rule catalog needs from a case's ICD diagnosis titles.

Case facts describe the patient record, never the model's plan (see `CASE_FACTS` in `plan.py`).
Ext-CDM does not store them as fields, so they are read from the coded diagnoses of the admission.
The matching uses the standard ICD-9 / ICD-10-CM title wording (public text), for example
"Biliary acute pancreatitis with infected necrosis", so it works on the `icd_diagnosis` text column
whether or not the code itself is present.

A fact is **omitted** from the result when the record cannot support it. The verifier then reports
"insufficient information" for the rules that need it, instead of passing on a guess.
See docs/case_facts_mapping.md for the source of every rule and what cannot be derived.
"""
from __future__ import annotations

import re
from typing import Iterable

# facts the record cannot give (no field or code in Ext-CDM / MIMIC-IV): never derived here
NOT_DERIVABLE = ("oral_or_enteral_feasible", "low_risk", "crc_screening_up_to_date")

_ORGAN_FAILURE = re.compile(r"\b(shock|respiratory failure|acute kidney failure|acute renal failure|severe sepsis|"
                            r"organ dysfunction|multiple organ)\b")
_BLEEDING = re.compile(r"(?<!without )\bbleeding\b|\bhemorrhage\b")
_ALARM = re.compile(r"(hemorrhage of anus and rectum|rectal bleeding|gastrointestinal hemorrhage|"
                    r"melena|hematochezia|iron deficiency anemia|abnormal weight loss|weight loss)")


def _texts(icd_titles: Iterable[str]) -> list[str]:
    return [" ".join(str(t).lower().split()) for t in icd_titles if str(t).strip()]


def _appendicitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "appendicitis" in t]
    if not rows:
        return {}
    complicated = any(re.search(r"peritonitis|abscess|perforat|gangren", t) for t in rows)
    return {"complicated": complicated}


def _pancreatitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "pancreatitis" in t]
    if not rows:
        return {}
    necrosis = any(re.search(r"with (uninfected|infected) necrosis", t) for t in rows)
    infected = any("with infected necrosis" in t for t in rows)
    facts = {
        "necrotizing": necrosis,
        "infection": infected or any("cholangitis" in t for t in texts),
        "biliary": any(re.search(r"biliary acute pancreatitis|gallstone pancreatitis", t) for t in rows),
        "cholangitis": any("cholangitis" in t for t in texts),
        "biliary_obstruction": any(re.search(r"obstruction of bile duct|bile duct.*with obstruction|"
                                            r"choledocholithiasis.*with obstruction", t) for t in texts),
        # mild = no necrosis and no coded organ failure (Atlanta-style: no local or systemic complication)
        "mild": not necrosis and not any(_ORGAN_FAILURE.search(t) for t in texts),
    }
    return facts


def _diverticulitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "diverticulitis" in t]
    if not rows:
        return {}
    # complicated = perforation, abscess or peritonitis coded for the bowel (ICD-10 K57.0/.2/.4/.8 titles, K65, 569.5, 569.83)
    related = [t for t in texts if re.search(r"diverticul|intestine|bowel|colon|peritone", t)]
    complicated = any(re.search(r"with perforation|abscess|peritonitis|perforation of intestine", t)
                      and "without perforation" not in t for t in related)
    alarm = any(_ALARM.search(t) for t in texts) or any(_BLEEDING.search(t) for t in rows)
    return {"complicated": complicated, "alarm_symptoms": alarm}


_BY_DIAGNOSIS = {"appendicitis": _appendicitis, "pancreatitis": _pancreatitis, "diverticulitis": _diverticulitis}


def derive_facts(diagnosis: str, icd_titles: Iterable[str]) -> dict[str, bool]:
    """Case facts for one admission. `diagnosis` is the Ext-CDM pathology; `icd_titles` its ICD diagnosis titles."""
    derive = _BY_DIAGNOSIS.get(diagnosis)
    return derive(_texts(icd_titles)) if derive else {}
