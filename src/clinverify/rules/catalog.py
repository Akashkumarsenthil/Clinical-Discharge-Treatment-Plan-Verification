"""Rule catalog v1.0 for team sign-off.

Rules check an LLM-generated discharge / treatment plan against recommendations from published guidelines, for the four
pathologies of the benchmark (appendicitis, cholecystitis, diverticulitis, pancreatitis). Every rule

  * cites the guideline and the statement number or section it comes from, and paraphrases what that statement says,
  * records the strength / quality of the recommendation as the guideline states it,
  * says when it applies, which plan fields and case facts it needs, and what happens if one is missing
    (the rule is inconclusive = "insufficient information"; a missing input never passes a plan),
  * has a violation message, one synthetic plan that satisfies it and one that violates it.

Sources (open-access full texts, read for this catalog; see docs/rule_catalog.md for the checklist):
  APP  Di Saverio et al. 2020, WSES Jerusalem guidelines for acute appendicitis, World J Emerg Surg 15:27
  CHO  Pisano et al. 2020, WSES guidelines for acute calculus cholecystitis, World J Emerg Surg 15:61
  PAN  Leppaniemi et al. 2019, WSES guidelines for severe acute pancreatitis, World J Emerg Surg 14:27
  DIV  Sartelli et al. 2020, WSES update on acute colonic diverticulitis in the emergency setting,
       World J Emerg Surg 15:32

Scope and limits (also in docs/rule_catalog.md): only recommendations that can be checked from a structured plan and
record facts are encoded; guidelines are from 2019-2020 and newer versions may differ; no clinician has reviewed the
set; the ASCRS 2020 diverticulitis guideline (paywalled) was not read. Hager et al. (2024) motivate the project but
their "essential treatment" list is NOT used as a source: it conflicts with these guidelines for uncomplicated cases.
"""
import z3

from clinverify.plan import DIAGNOSES, Plan
from clinverify.rules.base import RuleCatalog

CATALOG_VERSION = "1.0"

catalog = RuleCatalog()

APP = "WSES 2020 acute appendicitis guideline (Di Saverio et al., World J Emerg Surg 15:27)"
CHO = "WSES 2020 acute calculus cholecystitis guideline (Pisano et al., World J Emerg Surg 15:61)"
PAN = "WSES 2019 severe acute pancreatitis guideline (Leppaniemi et al., World J Emerg Surg 14:27)"
DIV = "WSES 2020 acute colonic diverticulitis update (Sartelli et al., World J Emerg Surg 15:32)"


# ------------------------------------------------------------------------------------------ helpers for examples
def _plan(case_id, diagnosis, treatments=(), days=None, hour=None, **facts):
    return Plan(case_id=case_id, diagnosis=diagnosis, treatments=tuple(treatments), postop_antibiotic_days=days,
                appendectomy_hour=hour, facts=dict(facts))


def _appendicitis(case_id, treatments=("appendectomy", "preoperative_antibiotic"), days=0, hour=12, **facts):
    base = dict(complicated=False, source_control_adequate=True, adult=True)
    return _plan(case_id, "appendicitis", treatments, days, hour, **{**base, **facts})


def _cholecystitis(case_id, treatments=("cholecystectomy",), days=0, **facts):
    base = dict(complicated=False, source_control_adequate=True, suitable_for_surgery=True)
    return _plan(case_id, "cholecystitis", treatments, days, None, **{**base, **facts})


def _pancreatitis(case_id, treatments=(), **facts):
    base = dict(infected=False, severe=False, mild=True, gallstone=False, cholangitis=False, cbd_obstruction=False)
    return _plan(case_id, "pancreatitis", treatments, None, None, **{**base, **facts})


def _diverticulitis(case_id, treatments=(), days=None, **facts):
    base = dict(immunocompetent=True, complicated=False, systemic_inflammation=False, source_control_adequate=True)
    return _plan(case_id, "diverticulitis", treatments, days, None, **{**base, **facts})


def _is(diagnosis):
    return lambda plan: plan.diagnosis == diagnosis


def _has(plan, treatment):
    return treatment in plan.treatments


def _fact(plan, key):
    return z3.BoolVal(bool(plan.facts[key]))


# =================================================================================================== general
@catalog.register(
    "R-GEN-001", "the plan states a diagnosis that this rule set covers",
    "Project scope: the four pathologies of MIMIC-IV-Ext-CDM (Hager et al. 2024, Nature Medicine 30:2613-2622)",
    requires=("diagnosis",),
    name="Diagnosis is in scope",
    recommendation="Not a clinical recommendation: the rules below exist only for appendicitis, cholecystitis, "
                   "diverticulitis and pancreatitis, so a plan for anything else cannot be verified by them.",
    strength="scope guard",
    applies_when="always",
    violation_message="The diagnosis is outside the rule set (appendicitis, cholecystitis, diverticulitis, pancreatitis); "
                      "no guideline rules exist for it.",
    valid_example=_appendicitis(1),
    invalid_example=_plan(2, "migraine"))
def r_gen_001(plan):
    return z3.BoolVal(plan.diagnosis in DIAGNOSES)


# ================================================================================================ appendicitis
@catalog.register(
    "R-APP-001", "an appendectomy plan includes a single preoperative dose of broad-spectrum antibiotic",
    f"{APP}, Recommendation 7.1", requires=(),
    name="Preoperative antibiotic dose before appendectomy",
    recommendation="Give a single preoperative dose of broad-spectrum antibiotics to patients with acute appendicitis "
                   "who undergo appendectomy.",
    strength="recommended (Recommendation 7.1; grade not shown beside this sentence)",
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    applies_when="diagnosis is appendicitis and an appendectomy is planned",
    violation_message="Appendectomy is planned without a preoperative antibiotic dose.",
    valid_example=_appendicitis(11),
    invalid_example=_appendicitis(12, treatments=("appendectomy",)))
def r_app_001(plan):
    return z3.BoolVal(_has(plan, "preoperative_antibiotic"))


@catalog.register(
    "R-APP-002", "no postoperative antibiotics after appendectomy for uncomplicated appendicitis",
    f"{APP}, Recommendation 7.1 (second sentence)", requires=("facts.complicated", "postop_antibiotic_days"),
    name="No postoperative antibiotics when uncomplicated",
    recommendation="Recommends against postoperative antibiotics for patients with uncomplicated appendicitis.",
    strength="strong, high-quality evidence (1A)",
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    applies_when="diagnosis is appendicitis and an appendectomy is planned",
    violation_message="Postoperative antibiotics are planned after appendectomy for uncomplicated appendicitis.",
    valid_example=_appendicitis(21),
    invalid_example=_appendicitis(22, days=3))
def r_app_002(plan):
    return z3.Implies(z3.Not(_fact(plan, "complicated")), z3.IntVal(plan.postop_antibiotic_days) == 0)


@catalog.register(
    "R-APP-003", "complicated appendicitis with adequate source control: postoperative antibiotics last at most 5 days",
    f"{APP}, Recommendation 7.2",
    requires=("facts.complicated", "facts.source_control_adequate", "postop_antibiotic_days"),
    name="Postoperative antibiotics not longer than 5 days (complicated)",
    recommendation="Recommends against prolonging postoperative antibiotics beyond 3-5 days in complicated "
                   "appendicitis when source control is adequate. The upper bound of 5 days is encoded.",
    strength="strong, high-quality evidence (1A)",
    applies=_is("appendicitis"),
    applies_when="diagnosis is appendicitis",
    violation_message="The postoperative antibiotic course is longer than 5 days although source control was adequate.",
    valid_example=_appendicitis(31, complicated=True, days=4),
    invalid_example=_appendicitis(32, complicated=True, days=7))
def r_app_003(plan):
    return z3.Implies(z3.And(_fact(plan, "complicated"), _fact(plan, "source_control_adequate")),
                      z3.IntVal(plan.postop_antibiotic_days) <= 5)


@catalog.register(
    "R-APP-004", "in adults, appendectomy takes place within 24 hours of admission",
    f"{APP}, Recommendation 3.2", requires=("facts.adult", "appendectomy_hour"),
    name="Appendectomy within 24 hours (adults)",
    recommendation="Recommends against delaying appendectomy beyond 24 hours from admission when surgery is needed. "
                   "(A separate weak suggestion exists for children; only adults are encoded.)",
    strength="strong, moderate-quality evidence (1B)",
    applies=lambda p: p.diagnosis == "appendicitis" and _has(p, "appendectomy"),
    applies_when="diagnosis is appendicitis and an appendectomy is planned",
    violation_message="Appendectomy is planned more than 24 hours after admission.",
    valid_example=_appendicitis(41, hour=20),
    invalid_example=_appendicitis(42, hour=30))
def r_app_004(plan):
    return z3.Implies(_fact(plan, "adult"), z3.IntVal(plan.appendectomy_hour) <= 24)


# =============================================================================================== cholecystitis
@catalog.register(
    "R-CHO-001", "no routine postoperative antibiotics after cholecystectomy for uncomplicated cholecystitis",
    f"{CHO}, Recommendation 7.1",
    requires=("facts.complicated", "facts.source_control_adequate", "postop_antibiotic_days"),
    name="No routine postoperative antibiotics when uncomplicated",
    recommendation="In uncomplicated acute calculus cholecystitis, recommends against routine postoperative antibiotics "
                   "when cholecystectomy controls the focus of infection.",
    strength="strong, high-quality evidence",
    applies=lambda p: p.diagnosis == "cholecystitis" and _has(p, "cholecystectomy"),
    applies_when="diagnosis is cholecystitis and a cholecystectomy is planned",
    violation_message="Postoperative antibiotics are planned after cholecystectomy for uncomplicated cholecystitis with "
                      "the infection source controlled.",
    valid_example=_cholecystitis(51),
    invalid_example=_cholecystitis(52, days=5))
def r_cho_001(plan):
    return z3.Implies(z3.And(z3.Not(_fact(plan, "complicated")), _fact(plan, "source_control_adequate")),
                      z3.IntVal(plan.postop_antibiotic_days) == 0)


@catalog.register(
    "R-CHO-002", "cholecystectomy is planned, or gallbladder drainage if the patient is not suitable for surgery",
    f"{CHO}, Recommendations 3.1 and 6.4", requires=("facts.suitable_for_surgery",),
    name="Cholecystectomy first-line; drainage if unsuitable for surgery",
    recommendation="Laparoscopic cholecystectomy is the first-line treatment (3.1); for patients not suitable for "
                   "surgery, gallbladder drainage is recommended (6.4).",
    strength="strong; high-quality (3.1) and moderate-quality (6.4) evidence",
    applies=_is("cholecystitis"),
    applies_when="diagnosis is cholecystitis",
    violation_message="The plan lacks the first-line treatment: cholecystectomy for a surgical candidate, or gallbladder "
                      "drainage for a patient not suitable for surgery.",
    valid_example=_cholecystitis(61, treatments=("gallbladder_drainage",), suitable_for_surgery=False),
    invalid_example=_cholecystitis(62, treatments=("gallbladder_drainage",)))
def r_cho_002(plan):
    suitable = _fact(plan, "suitable_for_surgery")
    return z3.And(z3.Implies(suitable, z3.BoolVal(_has(plan, "cholecystectomy"))),
                  z3.Implies(z3.Not(suitable), z3.BoolVal(_has(plan, "gallbladder_drainage"))))


# =============================================================================================== pancreatitis
@catalog.register(
    "R-PAN-001", "antibiotics for pancreatitis are given only when infection is documented",
    f"{PAN}, antimicrobial therapy section", requires=("facts.infected",),
    name="No routine prophylactic antibiotics",
    recommendation="Routine prophylactic antibiotics are no longer recommended for all patients with acute pancreatitis.",
    strength="strong evidence grade (1A)",
    applies=lambda p: p.diagnosis == "pancreatitis" and _has(p, "antibiotics"),
    applies_when="diagnosis is pancreatitis and antibiotics are planned",
    violation_message="Antibiotics are planned for pancreatitis without documented infection (routine prophylaxis).",
    valid_example=_pancreatitis(71, treatments=("antibiotics",), infected=True),
    invalid_example=_pancreatitis(72, treatments=("antibiotics",)))
def r_pan_001(plan):
    return _fact(plan, "infected")


@catalog.register(
    "R-PAN-002", "infected severe acute pancreatitis is treated with antibiotics",
    f"{PAN}, antimicrobial therapy section", requires=("facts.infected", "facts.severe"),
    name="Antibiotics for infected severe pancreatitis",
    recommendation="Antibiotics are always recommended to treat infected severe acute pancreatitis.",
    strength="stated as always recommended (grade not separately shown)",
    applies=_is("pancreatitis"),
    applies_when="diagnosis is pancreatitis",
    violation_message="The patient has infected severe pancreatitis but the plan contains no antibiotic treatment.",
    valid_example=_pancreatitis(81, treatments=("antibiotics", "enteral_nutrition"), severe=True, mild=False, infected=True),
    invalid_example=_pancreatitis(82, treatments=("enteral_nutrition",), severe=True, mild=False, infected=True))
def r_pan_002(plan):
    return z3.Implies(z3.And(_fact(plan, "severe"), _fact(plan, "infected")), z3.BoolVal(_has(plan, "antibiotics")))


@catalog.register(
    "R-PAN-003", "mild acute gallstone pancreatitis: cholecystectomy during the index admission",
    f"{PAN}, section on timing of cholecystectomy", requires=("facts.gallstone", "facts.mild"),
    name="Index-admission cholecystectomy (mild gallstone pancreatitis)",
    recommendation="Laparoscopic cholecystectomy during the index admission is recommended in mild acute gallstone "
                   "pancreatitis.",
    strength="strong evidence grade (1A)",
    applies=_is("pancreatitis"),
    applies_when="diagnosis is pancreatitis",
    violation_message="Mild gallstone pancreatitis: cholecystectomy during this admission is missing from the plan "
                      "(it should be done before discharge).",
    valid_example=_pancreatitis(91, treatments=("cholecystectomy_index_admission",), gallstone=True),
    invalid_example=_pancreatitis(92, gallstone=True))
def r_pan_003(plan):
    return z3.Implies(z3.And(_fact(plan, "gallstone"), _fact(plan, "mild")),
                      z3.BoolVal(_has(plan, "cholecystectomy_index_admission")))


@catalog.register(
    "R-PAN-004", "ERCP in gallstone pancreatitis only with cholangitis or bile duct obstruction",
    f"{PAN}, ERCP section", requires=("facts.gallstone", "facts.cholangitis", "facts.cbd_obstruction"),
    name="No routine ERCP in gallstone pancreatitis",
    recommendation="Routine ERCP in acute gallstone pancreatitis is not indicated (1A); it is indicated with cholangitis "
                   "(1B) and with common bile duct obstruction (2B).",
    strength="strong evidence grade (1A) for 'not routine'; 1B and 2B for the exceptions",
    applies=lambda p: p.diagnosis == "pancreatitis" and _has(p, "ercp"),
    applies_when="diagnosis is pancreatitis and ERCP is planned",
    violation_message="ERCP is planned for gallstone pancreatitis without cholangitis or common bile duct obstruction.",
    valid_example=_pancreatitis(101, treatments=("ercp",), gallstone=True, mild=False, cholangitis=True),
    invalid_example=_pancreatitis(102, treatments=("ercp",), gallstone=True, mild=False))
def r_pan_004(plan):
    return z3.Implies(_fact(plan, "gallstone"), z3.Or(_fact(plan, "cholangitis"), _fact(plan, "cbd_obstruction")))


@catalog.register(
    "R-PAN-005", "severe pancreatitis: the plan includes enteral nutrition",
    f"{PAN}, nutrition section", requires=("facts.severe",),
    name="Enteral nutrition in severe pancreatitis",
    recommendation="Enteral nutrition is recommended to prevent gut failure and infectious complications.",
    strength="recommended (grade not separately shown for this sentence)",
    applies=_is("pancreatitis"),
    applies_when="diagnosis is pancreatitis",
    violation_message="Severe pancreatitis: the plan contains no enteral nutrition.",
    valid_example=_pancreatitis(111, treatments=("enteral_nutrition",), severe=True, mild=False),
    invalid_example=_pancreatitis(112, severe=True, mild=False))
def r_pan_005(plan):
    return z3.Implies(_fact(plan, "severe"), z3.BoolVal(_has(plan, "enteral_nutrition")))


# ============================================================================================== diverticulitis
@catalog.register(
    "R-DIV-001", "no antibiotics for uncomplicated diverticulitis in an immunocompetent patient without systemic inflammation",
    f"{DIV}, antibiotic therapy statements",
    requires=("facts.immunocompetent", "facts.complicated", "facts.systemic_inflammation"),
    name="No antibiotics for uncomplicated diverticulitis",
    recommendation="In immunocompetent patients with uncomplicated diverticulitis without signs of systemic "
                   "inflammation, recommends not prescribing antibiotic therapy.",
    strength="strong, high-quality evidence (1A)",
    applies=lambda p: p.diagnosis == "diverticulitis" and _has(p, "antibiotics"),
    applies_when="diagnosis is diverticulitis and antibiotics are planned",
    violation_message="Antibiotics are planned for uncomplicated diverticulitis in an immunocompetent patient without "
                      "systemic inflammation.",
    valid_example=_diverticulitis(121, treatments=("antibiotics",), systemic_inflammation=True),
    invalid_example=_diverticulitis(122, treatments=("antibiotics",)))
def r_div_001(plan):
    no_antibiotics_group = z3.And(_fact(plan, "immunocompetent"), z3.Not(_fact(plan, "complicated")),
                                  z3.Not(_fact(plan, "systemic_inflammation")))
    return z3.Not(no_antibiotics_group)


@catalog.register(
    "R-DIV-002", "complicated diverticulitis with adequate source control: postoperative antibiotics last at most 4 days",
    f"{DIV}, postoperative antibiotic statement",
    requires=("facts.complicated", "facts.source_control_adequate", "postop_antibiotic_days"),
    name="Postoperative antibiotics about 4 days (complicated)",
    recommendation="Suggests a 4-day course of postoperative antibiotics in complicated diverticulitis when source "
                   "control has been adequate (stopping at 4 days was non-inferior to longer therapy).",
    strength="weak suggestion, moderate-quality evidence (2B): treat a violation as advisory",
    applies=lambda p: p.diagnosis == "diverticulitis" and p.postop_antibiotic_days is not None,
    applies_when="diagnosis is diverticulitis and a postoperative antibiotic course is stated",
    violation_message="The postoperative antibiotic course is longer than the suggested 4 days although source control "
                      "was adequate.",
    valid_example=_diverticulitis(131, days=4, complicated=True),
    invalid_example=_diverticulitis(132, days=7, complicated=True))
def r_div_002(plan):
    return z3.Implies(z3.And(_fact(plan, "complicated"), _fact(plan, "source_control_adequate")),
                      z3.IntVal(plan.postop_antibiotic_days) <= 4)
