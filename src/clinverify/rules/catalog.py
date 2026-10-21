"""The project's rule catalog (to be reviewed and owned by the team; owner: Sneha).

STATUS: DRAFT. These first rules were drafted from one source the team has read, Hager et al. (2024), and are listed
with their sources in docs/rule_catalog.md. Each must be checked against the cited source (and the guideline it cites)
and signed off by two team members before it is treated as final. They are NOT clinically validated.

Scope of this first set: for each of the four pathologies in the benchmark, the treatments that Hager et al. classify as
"essential" (given to every patient of that pathology, Fig. 4 and Methods, "Treatment requested"). Case-specific
treatments (appendectomy, cholecystectomy, colectomy, drainage, ERCP) depend on severity information that a plan
does not carry, so they are not encoded yet (see docs/rule_catalog.md).

Each rule says: if the plan's diagnosis is <pathology>, the plan must recommend <treatment>. Plans with any other
diagnosis satisfy the rule trivially. A plan must state its `diagnosis`; otherwise every rule is inconclusive. An empty `treatments` list means the plan
recommends nothing, which violates every rule for its diagnosis. Treatments are canonical concept names (plan.py).
"""
import z3

from clinverify.rules.base import RuleCatalog

catalog = RuleCatalog()

HAGER = "Hager et al. (2024), Nature Medicine 30:2613-2622, Fig. 4 and Methods ('Treatment requested')"
GUIDELINE = {
    "appendicitis": "WSES 2020 acute appendicitis guidelines (Di Saverio et al., World J Emerg Surg 15:27)",
    "cholecystitis": "WSES 2020 acute calculus cholecystitis guidelines (Pisano et al., World J Emerg Surg 15:61)",
    "diverticulitis": "ASCRS 2020 left-sided colonic diverticulitis guidelines (Hall et al., Dis Colon Rectum 63:728-747)",
    "pancreatitis": "WSES 2019 severe acute pancreatitis guidelines (Leppaniemi et al., World J Emerg Surg 14:27)",
}

# (rule id, diagnosis the rule applies to, treatment concept the plan must contain)
ESSENTIAL_TREATMENTS = [
    ("R-TRT-001", "appendicitis", "antibiotics"),
    ("R-TRT-002", "appendicitis", "support"),
    ("R-TRT-003", "cholecystitis", "antibiotics"),
    ("R-TRT-004", "cholecystitis", "support"),
    ("R-TRT-005", "diverticulitis", "antibiotics"),
    ("R-TRT-006", "diverticulitis", "support"),
    ("R-FUP-001", "diverticulitis", "future_colonoscopy"),     # Hager: models under-recommend a future colonoscopy
    ("R-TRT-007", "pancreatitis", "support"),
]


def _require_treatment(rule_id: str, diagnosis: str, treatment: str) -> None:
    shown = treatment.replace("_", " ")

    @catalog.register(rule_id,
                      f"a plan for {diagnosis} recommends {shown}",
                      f"{HAGER}: essential treatment for {diagnosis}; guideline cited there: {GUIDELINE[diagnosis]}",
                      requires=("diagnosis",))
    def _rule(plan, _d=diagnosis, _t=treatment):
        recommended = z3.Or([z3.StringVal(t) == z3.StringVal(_t) for t in plan.treatments] or [z3.BoolVal(False)])
        return z3.Implies(z3.BoolVal(plan.diagnosis == _d), recommended)


for _id, _diagnosis, _treatment in ESSENTIAL_TREATMENTS:
    _require_treatment(_id, _diagnosis, _treatment)
