"""Derive the case facts that the rule catalog needs from a case's ICD diagnosis titles and discharge diagnosis text.

Case facts describe the patient record, never the model's plan (see `CASE_FACTS` in `plan.py`).
Ext-CDM does not store them as fields, so they are read from the coded diagnoses of the admission.

Every fact has three possible outcomes:
  * present  -> True   (explicit evidence says so)
  * absent   -> False  (an explicit title says so, within what that title covers)
  * unknown  -> the key is left out of the result
Missing documentation is not evidence of absence. An unspecified title ("Acute pancreatitis", "Unspecified acute
appendicitis") or a phrase such as "without mention of hemorrhage" never produces False. A rule that needs an unknown
fact returns "insufficient information" instead of passing or failing on a guess.

Strict mode (default) follows that policy. `sensitivity=True` adds the absence-of-documentation assumptions
(no cholangitis / obstruction / infection coded = absent; mild with no organ failure coded) and must be reported as a
separate sensitivity analysis, never as the main result.

Evidence time point: ICD codes and the discharge diagnosis are assigned at discharge. They are retrospective record
evidence used to decide whether a plan follows the guideline for this patient, not information the model saw.

The matching uses the standard ICD-9 / ICD-10-CM title wording (public text). See docs/case_facts_mapping.md.
"""
from __future__ import annotations

import re
from typing import Iterable

# facts the record cannot give (no field or code in Ext-CDM / MIMIC-IV): never derived here
NOT_DERIVABLE = ("oral_or_enteral_feasible", "low_risk", "crc_screening_up_to_date")

_ORGAN_FAILURE = re.compile(r"\b(shock|respiratory failure|acute kidney failure|acute renal failure|severe sepsis|"
                            r"organ dysfunction|multiple organ)\b")
_LOCAL_COMPLICATION = re.compile(r"pseudocyst|fluid collection|pancreatic abscess|abscess of pancrea|necrosis of pancrea")
_INFECTION_TERMS = re.compile(r"infection|sepsis|septic|pneumonia|cholangitis|abscess|cellulitis|peritonitis|bacteremia|"
                              r"empyema|urinary tract")
_NEGATED = re.compile(r"without (perforation|abscess|gangrene)( or (perforation|abscess|gangrene))*")
_ALARM = re.compile(r"hemorrhage of anus and rectum|rectal bleeding|gastrointestinal hemorrhage|melena|hematochezia|"
                    r"iron deficiency anemia|weight loss|change in bowel habit")
# acute (bacterial) cholangitis only: primary sclerosing and primary biliary cholangitis are chronic autoimmune diseases
_CHOLANGITIS = re.compile(r"cholangitis")
_NOT_ACUTE_CHOLANGITIS = re.compile(r"sclerosing|primary biliary")

# discharge text: a complication counts only when it is written in the same clause as the target disease, is not
# negated (before or after it, including a negated list), is not historical, and is not attached to another organ
_HISTORY = re.compile(r"\b(history of|h/o|hx of|s/p|status post|prior|previous|resolved|remote)\b")
_NEGATION_CUE = re.compile(r"\b(no|not|without|negative for|denies|denied|rule[sd]? out|free of|absent|nor)\b")
_NEGATION_AFTER = re.compile(r"^\W*(\w+\W+){0,3}?(ruled out|excluded|negative|not seen|not present|absent|resolved)\b")
_NON_PREFIX = re.compile(r"\b(non|un)-?\s?(perforat\w*|gangren\w*|ruptur\w*|complicat\w*)")
_FILLER = {"evidence", "of", "signs", "sign", "findings", "finding", "concern", "for", "suspicion", "any", "a", "an", "the", "and",
           "or", "nor", "no", "current", "acute", "overt", "frank", "free", "fluid", "extraluminal", "air"}
_ASSERTION_BOUNDARIES = {"but", "however", "with", "though", "although", "plus", "except"}
_OTHER_SITE = {
    "appendicitis": r"gastric|duodenal|peptic|stomach|ulcer|gallbladder|cholecyst|diverticul|sigmoid|ovarian|uterine|bladder",
    # bladder, vaginal and uterine fistulas are diverticulitis complications (colovesical, colovaginal), so they are not excluded
    "diverticulitis": r"gastric|duodenal|peptic|stomach|ulcer|gallbladder|cholecyst|append|ovarian",
}


def _texts(icd_titles: Iterable[str]) -> list[str]:
    return [" ".join(str(t).lower().split()) for t in icd_titles if str(t).strip()]


def _negated_before(before: str, complication: str) -> bool:
    """A negation cue earlier in the clause covers this complication when only filler words or other complications
    (a negated list such as "without abscess, perforation or gangrene") lie between the cue and it."""
    cues = list(_NEGATION_CUE.finditer(before))
    if not cues:
        return False
    tokens = re.findall(r"[a-z]+", before[cues[-1].end():])
    # A new assertion ends the last negation's scope BEFORE either matching a list or a short noun phrase.
    # Otherwise "without abscess with perforation" incorrectly negates the documented perforation too.
    if set(tokens) & _ASSERTION_BOUNDARIES:
        return False
    if all(tok in _FILLER or re.match(complication, tok) or re.match(r"perforat|gangren|abscess|rupture|peritonitis|fistula|phlegmon|stricture", tok)
           for tok in tokens):
        return True                                            # a negated list: "without abscess, perforation or gangrene"
    # a short noun phrase between the cue and the complication ("without bladder fistula")
    return len(tokens) <= 3


def _written_complication(text: str, disease: str, complication: str, target: str) -> bool:
    """True if a clause of the discharge text names the disease together with a current, non-negated complication of
    that disease. Negation before or after, a negated list, "non-perforated", history and a complication attached to
    another organ ("perforated gastric ulcer") all give False."""
    other = re.compile(_OTHER_SITE[target])
    for clause in re.split(r"[;\n.]+", str(text or "").lower()):
        clause = " ".join(clause.split())
        clause = _NON_PREFIX.sub(" ", clause)
        if not re.search(disease, clause) or _HISTORY.search(clause):
            continue
        for m in re.finditer(complication, clause):
            if _negated_before(clause[:m.start()], complication) or _NEGATION_AFTER.search(clause[m.end():]):
                continue
            near = clause[max(0, m.start() - 25):m.end() + 25]
            if other.search(near):
                continue
            return True
    return False


def _appendicitis(texts: list[str], discharge: str, sensitivity: bool) -> dict[str, bool]:
    rows = [t for t in texts if "appendicitis" in t]
    if not rows:
        return {}
    # negated phrases ("without perforation or gangrene", ICD-10 K35.30 / K35.890) are removed before looking for complications
    cleaned = [_NEGATED.sub("", t) for t in rows]
    if any(re.search(r"perforat|gangren|abscess|generalized peritonitis", t) for t in cleaned):
        return {"complicated": True}
    if _written_complication(discharge, r"append", r"perforat\w*|gangren\w*|ruptur\w*|abscess\w*", "appendicitis"):   # text can only add True
        return {"complicated": True}
    if any(_NEGATED.search(t) for t in rows):          # an explicit "without perforation / gangrene / abscess" title
        return {"complicated": False}
    return {}                                          # "Unspecified acute appendicitis", "... without mention of peritonitis"


def _pancreatitis(texts: list[str], discharge: str, sensitivity: bool) -> dict[str, bool]:
    rows = [t for t in texts if "pancreatitis" in t]
    if not rows:
        return {}
    facts: dict[str, bool] = {}
    has_necrosis = any(re.search(r"with (uninfected|infected) necrosis", t) for t in rows)
    explicit_none = any("without necrosis or infection" in t for t in rows)      # ICD-10 K85.x0
    infected_necrosis = any("with infected necrosis" in t for t in rows)
    acute_cholangitis = any(_CHOLANGITIS.search(t) and not _NOT_ACUTE_CHOLANGITIS.search(t) for t in texts)
    obstruction = any(re.search(r"obstruction of bile duct|bile duct.*with obstruction|choledocholithiasis.*with obstruction", t)
                      for t in texts)
    if has_necrosis:
        facts["necrotizing"] = True
    elif explicit_none:
        facts["necrotizing"] = False
    if infected_necrosis or acute_cholangitis:
        facts["infection"] = True
    elif sensitivity and explicit_none and not any(_INFECTION_TERMS.search(t) for t in texts
                                                  if "without necrosis or infection" not in t):
        facts["infection"] = False                     # assumption: no infection coded anywhere
    if any(re.search(r"biliary acute pancreatitis|gallstone pancreatitis", t) for t in rows):
        facts["biliary"] = True
    elif any(re.search(r"idiopathic acute pancreatitis|alcohol induced acute pancreatitis|drug induced acute pancreatitis|"
                       r"other acute pancreatitis", t) for t in rows):
        facts["biliary"] = False                       # another cause is named
    if acute_cholangitis:
        facts["cholangitis"] = True
    elif sensitivity:
        facts["cholangitis"] = False                   # assumption: a diagnosis that is not coded is absent
    if obstruction:
        facts["biliary_obstruction"] = True
    elif sensitivity:
        facts["biliary_obstruction"] = False           # assumption
    # severity (Atlanta): mild needs no organ failure and no local or systemic complication, which codes cannot show.
    # Codes can show a severe feature (False). Mild stays unknown in strict mode.
    organ_failure = any(_ORGAN_FAILURE.search(t) for t in texts)
    local_complication = any(_LOCAL_COMPLICATION.search(t) for t in texts)
    if has_necrosis or organ_failure or local_complication:
        facts["mild"] = False
    elif sensitivity and explicit_none:
        facts["mild"] = True                           # assumption: no organ failure or local complication coded
    return facts


def _diverticulitis(texts: list[str], discharge: str, sensitivity: bool) -> dict[str, bool]:
    rows = [t for t in texts if "diverticulitis" in t]
    if not rows:
        return {}
    facts: dict[str, bool] = {}
    combined_yes = any(re.search(r"with perforation", t) and "without perforation" not in t for t in rows)
    # bowel or peritoneal complications coded next to the diverticulitis (ICD-9 has no combined code); the link to the
    # diverticulitis is assumed because the admission's primary diagnosis is diverticulitis
    separate = any(re.search(r"abscess of intestine|perforation of intestine|peritonitis|phlegmon|"
                             r"fistula of intestine|colovesical fistula|vesicointestinal fistula|"
                             r"stricture of (colon|intestine)|stenosis of (colon|intestine)|obstruction of intestine", t)
                   for t in texts)
    written = _written_complication(discharge, r"diverticul", r"perforat\w*|abscess\w*|peritonitis|fistula\w*|phlegmon|stricture", "diverticulitis")
    combined_no = any("without perforation or abscess" in t for t in rows)
    if combined_yes or separate or written:
        facts["complicated"] = True
    elif combined_no:
        facts["complicated"] = False
    # alarm symptoms: only explicit presence counts. "without bleeding" or "without mention of hemorrhage" rule nothing in or out
    with_bleeding = any(re.search(r"(?<!without )(?<!without mention of )\b(bleeding|hemorrhage)\b", t) for t in rows)
    if with_bleeding or any(_ALARM.search(t) for t in texts):
        facts["alarm_symptoms"] = True
    return facts


_BY_DIAGNOSIS = {"appendicitis": _appendicitis, "pancreatitis": _pancreatitis, "diverticulitis": _diverticulitis}


def derive_facts(diagnosis: str, icd_titles: Iterable[str], discharge_diagnosis: str = "", sensitivity: bool = False) -> dict[str, bool]:
    """Case facts for one admission. `diagnosis` is the Ext-CDM pathology; `icd_titles` its ICD diagnosis titles;
    `discharge_diagnosis` the discharge diagnosis text, used only to add a written, current, non-negated complication
    of the target disease (never to rule one out). `sensitivity=True` adds the absence-of-documentation assumptions.
    Facts that cannot be established are not in the result."""
    derive = _BY_DIAGNOSIS.get(diagnosis)
    return derive(_texts(icd_titles), str(discharge_diagnosis or ""), sensitivity) if derive else {}
