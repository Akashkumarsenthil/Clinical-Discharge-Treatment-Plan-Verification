"""Derive the case facts that the rule catalog needs from a case's ICD diagnosis titles.

Case facts describe the patient record, never the model's plan (see `CASE_FACTS` in `plan.py`).
Ext-CDM does not store them as fields, so they are read from the coded diagnoses of the admission.

Every fact has three possible outcomes:
  * present  -> True   (an explicit title says so)
  * absent   -> False  (an explicit title says so, within what that title covers)
  * unknown  -> the key is left out of the result
An unspecified title ("Acute pancreatitis", "Unspecified acute appendicitis") or a phrase such as "without mention of
hemorrhage" does not establish absence, so it never produces False. A rule that needs an unknown fact returns
"insufficient information" instead of passing or failing on a guess.

The matching uses the standard ICD-9 / ICD-10-CM title wording (public text) on the `icd_diagnosis` text column.
See docs/case_facts_mapping.md for the source of every rule and what cannot be derived.
"""
from __future__ import annotations

import re
from typing import Iterable

# facts the record cannot give (no field or code in Ext-CDM / MIMIC-IV): never derived here
NOT_DERIVABLE = ("oral_or_enteral_feasible", "low_risk", "crc_screening_up_to_date")

_ORGAN_FAILURE = re.compile(r"\b(shock|respiratory failure|acute kidney failure|acute renal failure|severe sepsis|"
                            r"organ dysfunction|multiple organ)\b")
_INFECTION_TERMS = re.compile(r"infection|sepsis|septic|pneumonia|cholangitis|abscess|cellulitis|peritonitis|bacteremia|"
                              r"empyema|urinary tract")
_NEGATED = re.compile(r"without (perforation|abscess|gangrene)( or (perforation|abscess|gangrene))*")
_ALARM = re.compile(r"hemorrhage of anus and rectum|rectal bleeding|gastrointestinal hemorrhage|melena|hematochezia|"
                    r"iron deficiency anemia|weight loss")


def _texts(icd_titles: Iterable[str]) -> list[str]:
    return [" ".join(str(t).lower().split()) for t in icd_titles if str(t).strip()]


def _appendicitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "appendicitis" in t]
    if not rows:
        return {}
    # negated phrases ("without perforation or gangrene", ICD-10 K35.30 / K35.890) are removed before looking for complications
    cleaned = [_NEGATED.sub("", t) for t in rows]
    if any(re.search(r"perforat|gangren|abscess|generalized peritonitis", t) for t in cleaned):
        return {"complicated": True}
    if any(_NEGATED.search(t) for t in rows):          # an explicit "without perforation / gangrene / abscess" title
        return {"complicated": False}
    return {}                                          # "Unspecified acute appendicitis", "... without mention of peritonitis"


def _pancreatitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "pancreatitis" in t]
    if not rows:
        return {}
    facts: dict[str, bool] = {}
    has_necrosis = any(re.search(r"with (uninfected|infected) necrosis", t) for t in rows)
    explicit_none = any("without necrosis or infection" in t for t in rows)      # ICD-10 K85.x0
    infected_necrosis = any("with infected necrosis" in t for t in rows)
    cholangitis = any("cholangitis" in t for t in texts)
    if has_necrosis:
        facts["necrotizing"] = True
    elif explicit_none:
        facts["necrotizing"] = False
    if infected_necrosis or cholangitis:
        facts["infection"] = True
    elif explicit_none and not any(_INFECTION_TERMS.search(t) for t in texts if "without necrosis or infection" not in t):
        facts["infection"] = False                                               # no infection coded anywhere
    if any(re.search(r"biliary acute pancreatitis|gallstone pancreatitis", t) for t in rows):
        facts["biliary"] = True
    elif any(re.search(r"idiopathic acute pancreatitis|alcohol induced acute pancreatitis|drug induced acute pancreatitis|"
                       r"other acute pancreatitis", t) for t in rows):
        facts["biliary"] = False                                                 # another cause is named
    # cholangitis and bile-duct obstruction are diagnoses that are coded when present
    facts["cholangitis"] = cholangitis
    facts["biliary_obstruction"] = any(re.search(r"obstruction of bile duct|bile duct.*with obstruction|"
                                                 r"choledocholithiasis.*with obstruction", t) for t in texts)
    # severity (Atlanta): mild needs no organ failure and no local complication. Codes can show a severe feature
    # (False) or, with an explicit "without necrosis or infection" title and no organ failure coded, support mild (True).
    organ_failure = any(_ORGAN_FAILURE.search(t) for t in texts)
    if has_necrosis or organ_failure:
        facts["mild"] = False
    elif explicit_none:
        facts["mild"] = True
    return facts


def _diverticulitis(texts: list[str]) -> dict[str, bool]:
    rows = [t for t in texts if "diverticulitis" in t]
    if not rows:
        return {}
    facts: dict[str, bool] = {}
    combined_yes = any(re.search(r"with perforation", t) and "without perforation" not in t for t in rows)
    # bowel or peritoneal complications coded next to the diverticulitis (ICD-9 has no combined code); the link to the
    # diverticulitis is assumed because the admission's primary diagnosis is diverticulitis
    separate = any(re.search(r"abscess of intestine|perforation of intestine|peritonitis", t) for t in texts)
    combined_no = any("without perforation or abscess" in t for t in rows)
    if combined_yes or separate:
        facts["complicated"] = True
    elif combined_no:
        facts["complicated"] = False
    # alarm symptoms: only explicit presence counts. "without bleeding" or "without mention of hemorrhage" rule nothing in or out
    with_bleeding = any(re.search(r"(?<!without )(?<!without mention of )\b(bleeding|hemorrhage)\b", t) for t in rows)
    if with_bleeding or any(_ALARM.search(t) for t in texts):
        facts["alarm_symptoms"] = True
    return facts


_BY_DIAGNOSIS = {"appendicitis": _appendicitis, "pancreatitis": _pancreatitis, "diverticulitis": _diverticulitis}


def derive_facts(diagnosis: str, icd_titles: Iterable[str]) -> dict[str, bool]:
    """Case facts for one admission. `diagnosis` is the Ext-CDM pathology; `icd_titles` its ICD diagnosis titles.
    Facts that cannot be established are not in the result."""
    derive = _BY_DIAGNOSIS.get(diagnosis)
    return derive(_texts(icd_titles)) if derive else {}
