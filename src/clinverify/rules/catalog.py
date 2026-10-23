"""Rule catalog v2.0 for team sign-off. All sources are from 2025-2026.

Rules check an LLM-generated discharge / treatment plan against recommendations in recent published guidelines. The course
asks for sources no more than 3-4 years old, so only guidelines from 2025-2026 are used; rules that rested on older
guidelines (WSES 2019-2020) were removed or deferred (see docs/rule_catalog.md). Every rule

  * cites the guideline, what part of it was read (full text or abstract) and the section it comes from,
  * paraphrases the recommendation and records its strength / quality as the guideline states it,
  * says when it applies, which plan fields and case facts it needs, and what happens when one is missing
    (the rule is inconclusive = "insufficient information"; a missing input never passes a plan),
  * is marked advisory when its source only suggests (a violation is flagged, not treated as a hard failure),
  * has a violation message, one synthetic plan that satisfies it and one that violates only this rule.

Sources (full references in docs/rule_catalog.md):
  SWE     Salo et al. 2025, Swedish national guidelines for acute appendicitis, BJS Open 9:zrae165 (open access, full text read)
  WSES25  Podda et al. 2026, 2025 WSES Jerusalem guidelines for acute appendicitis, JAMA Surg 161:283-295 (abstract read; paywalled)
  ILATAM  Cardenas-Jaen et al. 2026, Ibero-Latin American guidelines on acute pancreatitis, UEG J 14:e70190 (open access, full text read)
  ACG26   Peery et al. 2026, ACG clinical guideline: colonic diverticulitis, Am J Gastroenterol 121:1549-1561 (abstract read; paywalled)
  KASID26 Lee et al. 2026, Korean guidelines for acute colonic diverticulitis, Intest Res 24:428-463 (open access, full text read)

Scope and limits (also in docs/rule_catalog.md): cholecystitis has no rules yet because no general guideline from the last
four years could be read; no clinician has reviewed the set; case facts must come from the record, not from the model.
Hager et al. (2024) motivate the project but their "essential treatment" list is NOT used as a source.
"""
import z3

from clinverify.plan import Plan
from clinverify.rules.base import RuleCatalog

CATALOG_VERSION = "2.1"
COVERED_DIAGNOSES = ("appendicitis", "pancreatitis", "diverticulitis")

catalog = RuleCatalog()

SWE = "Swedish national guidelines for acute appendicitis (Salo et al., BJS Open 2025;9:zrae165; full text)"
WSES25 = "2025 WSES Jerusalem guidelines for acute appendicitis (Podda et al., JAMA Surg 2026;161:283-295; abstract only)"
ILATAM = "Ibero-Latin American guidelines on acute pancreatitis (Cardenas-Jaen et al., UEG J 2026;14:e70190; full text)"
ACG26 = "ACG clinical guideline on colonic diverticulitis (Peery et al., Am J Gastroenterol 2026;121:1549-1561; abstract only)"
KASID26 = "Korean guidelines for acute colonic diverticulitis (Lee et al., Intest Res 2026;24:428-463; full text)"


# ------------------------------------------------------------------------------------------ helpers for examples
def _plan(case_id, diagnosis, treatments=(), days=None, **facts):
    return Plan(case_id=case_id, diagnosis=diagnosis, treatments=tuple(treatments), postop_antibiotic_days=days, facts=dict(facts))


def _appendicitis(case_id, treatments=("appendectomy", "preoperative_antibiotic"), days=0, **facts):
    return _plan(case_id, "appendicitis", treatments, days, **{**dict(complicated=False), **facts})


def _pancreatitis(case_id, treatments=(), **facts):
    base = dict(infection=False, necrotizing=False, mild=True, biliary=False, cholangitis=False, biliary_obstruction=False,
                oral_or_enteral_feasible=True)
    return _plan(case_id, "pancreatitis", treatments, None, **{**base, **facts})


def _diverticulitis(case_id, treatments=(), **facts):
    base = dict(complicated=False, low_risk=True, alarm_symptoms=False, crc_screening_up_to_date=True)
    return _plan(case_id, "diverticulitis", treatments, None, **{**base, **facts})


def _is(diagnosis):
    return lambda plan: plan.diagnosis == diagnosis


def _has(plan, treatment):
    return treatment in plan.treatments


def _fact(plan, key):
    return z3.BoolVal(bool(plan.facts[key]))


def _div_003_requires(plan):
    """Known alarm symptoms already establish the colonoscopy indication, so screening history is then not needed."""
    if plan.facts.get("alarm_symptoms") is True:
        return ("facts.complicated", "facts.alarm_symptoms")
    return ("facts.complicated", "facts.alarm_symptoms", "facts.crc_screening_up_to_date")


# =================================================================================================== general
@catalog.register(
    "R-GEN-001", "the plan states a diagnosis that this rule set covers",
    "Project scope: the rule set covers appendicitis, pancreatitis and diverticulitis (benchmark pathologies of Hager et al. 2024)",
    requires=("diagnosis",),
    name="Diagnosis is covered by the rules",
    recommendation="Not a clinical recommendation: a plan for any other diagnosis cannot be verified by the rules below. "
                   "Cholecystitis is a benchmark pathology but has no rules yet (no recent general guideline could be read).",
    strength="scope guard", applies_when="always", source_date="2026",
    violation_message="No guideline rules exist for this diagnosis (covered: appendicitis, pancreatitis, diverticulitis).",
    valid_example=_appendicitis(1),
    invalid_example=_plan(2, "cholecystitis"))
def r_gen_001(plan):
    return z3.BoolVal(plan.diagnosis in COVERED_DIAGNOSES)


# ================================================================================================ appendicitis
@catalog.register(
    "R-APP-001", "an appendectomy plan includes a dose of broad-spectrum antibiotic as prophylaxis",
    f"{SWE}, antibiotic recommendations for appendectomy", requires=(),
    name="Antibiotic prophylaxis for appendectomy",
    recommendation="A dose of broad-spectrum antibiotics should be given as prophylaxis for appendectomy.",
    strength="GRADE high certainty of evidence (four-plus rating)", source_date="2025",
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    applies_when="diagnosis is appendicitis and an appendectomy is planned",
    violation_message="Appendectomy is planned without antibiotic prophylaxis.",
    valid_example=_appendicitis(11),
    invalid_example=_appendicitis(12, treatments=("appendectomy",)))
def r_app_001(plan):
    return z3.BoolVal(_has(plan, "preoperative_antibiotic"))


@catalog.register(
    "R-APP-002", "no postoperative antibiotics after surgery for uncomplicated appendicitis",
    f"{SWE}, antibiotic recommendations for appendectomy", requires=("facts.complicated", "postop_antibiotic_days"),
    name="No postoperative antibiotics when uncomplicated",
    recommendation="No postoperative antibiotics should be given in surgery for uncomplicated appendicitis.",
    strength="GRADE high certainty of evidence (four-plus rating)", source_date="2025",
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    condition_facts=(("complicated", False),),
    applies_when="diagnosis is appendicitis, an appendectomy is planned and the appendicitis is uncomplicated",
    violation_message="Postoperative antibiotics are planned after surgery for uncomplicated appendicitis.",
    valid_example=_appendicitis(21),
    invalid_example=_appendicitis(22, days=3))
def r_app_002(plan):
    return z3.Implies(z3.Not(_fact(plan, "complicated")), z3.IntVal(plan.postop_antibiotic_days) == 0)


@catalog.register(
    "R-APP-003", "complicated appendicitis with surgery: a postoperative antibiotic course, if given, is at most 3 days",
    f"{WSES25}, key findings in the abstract", requires=("facts.complicated", "postop_antibiotic_days"),
    name="Postoperative antibiotic course of at most 3 days (complicated)",
    recommendation="Postoperative antibiotic therapy should be limited to short courses (2-3 days) in complicated "
                   "appendicitis. Only the upper bound of 3 days is encoded: the rule does not check that antibiotics are indicated "
                   "(zero days passes). The Swedish 2025 guideline says there is no full consensus on the duration, so a "
                   "violation is advisory.",
    strength="stated in the abstract of the 2025 edition; grade not shown there", source_date="2026", advisory=True,
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    condition_facts=(("complicated", True),),
    applies_when="diagnosis is appendicitis, an appendectomy is planned and the appendicitis is complicated",
    violation_message="The postoperative antibiotic course is longer than the 2-3 days suggested for complicated appendicitis.",
    valid_example=_appendicitis(31, complicated=True, days=3),
    invalid_example=_appendicitis(32, complicated=True, days=7))
def r_app_003(plan):
    return z3.Implies(_fact(plan, "complicated"), z3.IntVal(plan.postop_antibiotic_days) <= 3)


# =============================================================================================== pancreatitis
@catalog.register(
    "R-PAN-001", "antibiotics for acute pancreatitis are planned only for suspected or confirmed infection",
    f"{ILATAM}, antibiotic recommendations", requires=("facts.infection",),
    name="No prophylactic antibiotics",
    recommendation="Antibiotic treatment should be reserved for suspected or confirmed infected pancreatic necrosis, "
                   "acute cholangitis or other extrapancreatic infection; routine prophylactic antibiotics are not recommended.",
    strength="strong recommendation, high-quality evidence", source_date="2026",
    applies=lambda p: p.diagnosis == "pancreatitis" and _has(p, "antibiotics"),
    applies_when="diagnosis is pancreatitis and antibiotics are planned",
    violation_message="Antibiotics are planned for pancreatitis without suspected or confirmed infection (prophylaxis).",
    valid_example=_pancreatitis(71, treatments=("antibiotics",), infection=True),
    invalid_example=_pancreatitis(72, treatments=("antibiotics",)))
def r_pan_001(plan):
    return _fact(plan, "infection")


@catalog.register(
    "R-PAN-002", "necrotizing pancreatitis with confirmed or strongly suspected infection is treated with antibiotics",
    f"{ILATAM}, explanatory text of the antibiotic recommendations", requires=("facts.necrotizing", "facts.infection"),
    name="Empiric antibiotics for infected necrotizing pancreatitis",
    recommendation="Empiric antibiotics must be initiated in necrotizing pancreatitis with confirmed or strongly "
                   "suspected infection.",
    strength="stated in the explanatory text; no strength label shown beside this sentence", source_date="2026",
    applies=_is("pancreatitis"), condition_facts=(("necrotizing", True), ("infection", True)),
    applies_when="diagnosis is pancreatitis with necrosis and infection",
    violation_message="Necrotizing pancreatitis with confirmed or strongly suspected infection: the plan has no antibiotic treatment.",
    valid_example=_pancreatitis(81, treatments=("antibiotics",), necrotizing=True, infection=True, mild=False),
    invalid_example=_pancreatitis(82, necrotizing=True, infection=True, mild=False))
def r_pan_002(plan):
    return z3.Implies(z3.And(_fact(plan, "necrotizing"), _fact(plan, "infection")), z3.BoolVal(_has(plan, "antibiotics")))


@catalog.register(
    "R-PAN-003", "mild biliary pancreatitis: cholecystectomy during the index hospitalization",
    f"{ILATAM}, cholecystectomy recommendations", requires=("facts.biliary", "facts.mild"),
    name="Cholecystectomy during the index admission (mild biliary pancreatitis)",
    recommendation="For patients with mild acute pancreatitis, laparoscopic cholecystectomy should be performed during "
                   "the index hospitalization (so it belongs in the discharge plan before discharge). In moderate to "
                   "severe disease it is delayed until 8 weeks after discharge or until local complications resolve.",
    strength="strong recommendation, high-quality evidence", source_date="2026",
    applies=_is("pancreatitis"), condition_facts=(("biliary", True), ("mild", True)),
    applies_when="diagnosis is mild biliary pancreatitis",
    violation_message="Mild biliary pancreatitis: cholecystectomy during this admission is missing from the plan.",
    valid_example=_pancreatitis(91, treatments=("cholecystectomy_during_admission",), biliary=True),
    invalid_example=_pancreatitis(92, biliary=True))
def r_pan_003(plan):
    return z3.Implies(z3.And(_fact(plan, "biliary"), _fact(plan, "mild")),
                      z3.BoolVal(_has(plan, "cholecystectomy_during_admission")))


@catalog.register(
    "R-PAN-004", "ERCP in biliary pancreatitis is planned only with cholangitis or ongoing biliary obstruction",
    f"{ILATAM}, ERCP recommendations and explanatory text", requires=("facts.biliary", "facts.cholangitis", "facts.biliary_obstruction"),
    name="ERCP only for cholangitis or biliary obstruction",
    recommendation="Urgent ERCP (within 24 hours) is strongly recommended for biliary pancreatitis with cholangitis; in "
                   "choledocholithiasis without cholangitis ERCP may be delayed. The explanatory text says ERCP is "
                   "discouraged without cholangitis or biliary obstruction (within 72 hours for ongoing obstruction).",
    strength="strong, high-quality evidence for urgent ERCP with cholangitis; weak, moderate-quality evidence for delaying "
             "it without cholangitis. The 'discouraged' wording is advisory.", source_date="2026", advisory=True,
    applies=lambda p: p.diagnosis == "pancreatitis" and _has(p, "ercp"), condition_facts=(("biliary", True),),
    applies_when="diagnosis is biliary pancreatitis and ERCP is planned",
    violation_message="ERCP is planned for biliary pancreatitis without cholangitis or ongoing biliary obstruction.",
    valid_example=_pancreatitis(101, treatments=("ercp",), biliary=True, mild=False, cholangitis=True),
    invalid_example=_pancreatitis(102, treatments=("ercp",), biliary=True, mild=False))
def r_pan_004(plan):
    return z3.Implies(_fact(plan, "biliary"), z3.Or(_fact(plan, "cholangitis"), _fact(plan, "biliary_obstruction")))


@catalog.register(
    "R-PAN-005", "parenteral nutrition is planned only when oral and enteral feeding are not feasible",
    f"{ILATAM}, nutrition recommendations", requires=("facts.oral_or_enteral_feasible",),
    name="Parenteral nutrition only as a last resort",
    recommendation="Early oral feeding is preferred; enteral tube feeding if oral intake is not tolerated after 3-4 days; "
                   "parenteral nutrition should be reserved for cases in which oral and enteral nutrition are not feasible.",
    strength="strong recommendation, high-quality evidence", source_date="2026",
    applies=lambda p: p.diagnosis == "pancreatitis" and _has(p, "parenteral_nutrition"),
    applies_when="diagnosis is pancreatitis and parenteral nutrition is planned",
    violation_message="Parenteral nutrition is planned although oral or enteral feeding is feasible.",
    valid_example=_pancreatitis(111, treatments=("parenteral_nutrition",), oral_or_enteral_feasible=False),
    invalid_example=_pancreatitis(112, treatments=("parenteral_nutrition",)))
def r_pan_005(plan):
    return z3.Not(_fact(plan, "oral_or_enteral_feasible"))


# ============================================================================================== diverticulitis
@catalog.register(
    "R-DIV-001", "no routine antibiotics for acute uncomplicated diverticulitis in low-risk patients",
    f"{ACG26}, recommendation on antibiotics; {KASID26}, antibiotic recommendation for uncomplicated diverticulitis",
    requires=("facts.complicated", "facts.low_risk"),
    name="No routine antibiotics when uncomplicated and low risk",
    recommendation="ACG 2026 suggests against routine antibiotics for low-risk patients with acute uncomplicated "
                   "diverticulitis because trials show little or no benefit. The Korean 2026 guideline says that in "
                   "patients who are not immunocompromised, conservative management without antibiotics may be considered.",
    strength="ACG: suggestion; KASID: conditional recommendation, high-quality evidence. Advisory.", source_date="2026",
    advisory=True,
    applies=lambda p: p.diagnosis == "diverticulitis" and _has(p, "antibiotics"),
    condition_facts=(("complicated", False), ("low_risk", True)),
    applies_when="diagnosis is uncomplicated diverticulitis in a low-risk patient and antibiotics are planned",
    violation_message="Routine antibiotics are planned for uncomplicated diverticulitis in a low-risk patient.",
    valid_example=_diverticulitis(121, treatments=("antibiotics",), low_risk=False),
    invalid_example=_diverticulitis(122, treatments=("antibiotics",)))
def r_div_001(plan):
    return z3.Not(z3.And(z3.Not(_fact(plan, "complicated")), _fact(plan, "low_risk")))


@catalog.register(
    "R-DIV-002", "complicated diverticulitis: the plan includes a colonoscopy after recovery",
    f"{ACG26}, recommendation on colonoscopy after diverticulitis", requires=("facts.complicated",),
    name="Colonoscopy after complicated diverticulitis",
    recommendation="After recovery, colonoscopy is recommended for patients with complicated diverticulitis to rule out "
                   "an underlying malignancy.",
    strength="recommended (wording of the abstract; strength label not read)", source_date="2026",
    applies=_is("diverticulitis"), condition_facts=(("complicated", True),),
    applies_when="diagnosis is complicated diverticulitis",
    violation_message="Complicated diverticulitis: no colonoscopy after recovery is planned.",
    valid_example=_diverticulitis(131, treatments=("colonoscopy_after_recovery",), complicated=True),
    invalid_example=_diverticulitis(132, complicated=True))
def r_div_002(plan):
    return z3.Implies(_fact(plan, "complicated"), z3.BoolVal(_has(plan, "colonoscopy_after_recovery")))


@catalog.register(
    "R-DIV-003", "uncomplicated diverticulitis with alarm symptoms or overdue colorectal cancer screening: colonoscopy after recovery",
    f"{ACG26}, recommendation on colonoscopy after diverticulitis",
    requires=("facts.complicated", "facts.alarm_symptoms", "facts.crc_screening_up_to_date"),
    name="Colonoscopy suggested after uncomplicated diverticulitis in selected patients",
    recommendation="After recovery, colonoscopy is suggested for patients with uncomplicated diverticulitis who have "
                   "alarm symptoms or are not up to date with colorectal cancer screening.",
    strength="suggested (wording of the abstract; strength label not read). Advisory.", source_date="2026", advisory=True,
    applies=_is("diverticulitis"), condition_facts=(("complicated", False),), requires_for=_div_003_requires,
    applies_when="diagnosis is uncomplicated diverticulitis",
    violation_message="Uncomplicated diverticulitis with alarm symptoms or overdue screening: no colonoscopy is planned.",
    valid_example=_diverticulitis(141, treatments=("colonoscopy_after_recovery",), alarm_symptoms=True),
    invalid_example=_diverticulitis(142, alarm_symptoms=True))
def r_div_003(plan):
    # known alarm symptoms are enough; otherwise screening history is also known (see _div_003_requires)
    indication = z3.Or(z3.BoolVal(plan.facts.get("alarm_symptoms") is True),
                       z3.BoolVal(plan.facts.get("crc_screening_up_to_date") is False))
    needs = z3.And(z3.Not(_fact(plan, "complicated")), indication)
    return z3.Implies(needs, z3.BoolVal(_has(plan, "colonoscopy_after_recovery")))
