"""Case-fact derivation from ICD titles (public title wording only, no patient data).

Each fact is present (True), explicitly absent (False) or unknown (key left out)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clinverify.data.case_facts import NOT_DERIVABLE, derive_facts  # noqa: E402


def test_appendicitis_complicated_present_absent_unknown():
    assert derive_facts("appendicitis", ["Acute appendicitis with generalized peritonitis"]) == {"complicated": True}
    assert derive_facts("appendicitis", ["Acute appendicitis with peritoneal abscess"]) == {"complicated": True}
    assert derive_facts("appendicitis", ["Acute appendicitis with localized peritonitis and gangrene"]) == {"complicated": True}
    assert derive_facts("appendicitis", ["Acute appendicitis with localized peritonitis, perforation, or gangrene"]) == {"complicated": True}
    # explicit absence
    assert derive_facts("appendicitis", ["Acute appendicitis with localized peritonitis, without perforation or gangrene"]) == {"complicated": False}
    assert derive_facts("appendicitis", ["Other acute appendicitis without perforation or gangrene"]) == {"complicated": False}
    # unspecified or "without mention" does not establish absence
    assert derive_facts("appendicitis", ["Unspecified acute appendicitis"]) == {}
    assert derive_facts("appendicitis", ["Acute appendicitis without mention of peritonitis"]) == {}


def test_generic_pancreatitis_leaves_everything_unknown():
    f = derive_facts("pancreatitis", ["Acute pancreatitis"])
    assert "necrotizing" not in f and "infection" not in f and "biliary" not in f and "mild" not in f


def test_pancreatitis_explicit_titles():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis with infected necrosis"])
    assert f["necrotizing"] is True and f["infection"] is True and f["biliary"] is True and f["mild"] is False
    g = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection"])
    assert g["biliary"] is True and g["necrotizing"] is False
    assert "infection" not in g and "mild" not in g                  # strict mode: not established by this title alone
    h = derive_facts("pancreatitis", ["Idiopathic acute pancreatitis with uninfected necrosis"])
    assert h["necrotizing"] is True and h["biliary"] is False and h["mild"] is False
    assert "infection" not in h                      # uninfected necrosis does not rule out an infection elsewhere


def test_mild_pancreatitis_is_never_inferred_in_strict_mode():
    titles = ["Biliary acute pancreatitis without necrosis or infection"]
    assert "mild" not in derive_facts("pancreatitis", titles)
    # a local complication coded next to it shows it is not mild
    assert derive_facts("pancreatitis", titles + ["Pseudocyst of pancreas"])["mild"] is False
    assert derive_facts("pancreatitis", titles + ["Acute kidney failure"])["mild"] is False


def test_strict_mode_leaves_undocumented_facts_unknown_and_sensitivity_mode_adds_the_assumptions():
    titles = ["Idiopathic acute pancreatitis without necrosis or infection"]
    strict = derive_facts("pancreatitis", titles)
    assert "infection" not in strict and "cholangitis" not in strict and "biliary_obstruction" not in strict
    sens = derive_facts("pancreatitis", titles, sensitivity=True)
    assert sens["infection"] is False and sens["cholangitis"] is False and sens["biliary_obstruction"] is False
    assert sens["mild"] is True
    # an infection-type diagnosis blocks the assumption even in sensitivity mode
    assert "infection" not in derive_facts("pancreatitis", titles + ["Pneumonia, unspecified organism"], sensitivity=True)


def test_cholangitis_and_obstruction_only_when_documented():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection",
                                      "Cholangitis, unspecified", "Obstruction of bile duct"])
    assert f["cholangitis"] is True and f["infection"] is True and f["biliary_obstruction"] is True
    g = derive_facts("pancreatitis", ["Acute pancreatitis"])
    assert "cholangitis" not in g and "biliary_obstruction" not in g


def test_primary_sclerosing_cholangitis_is_not_acute_cholangitis():
    f = derive_facts("pancreatitis", ["Idiopathic acute pancreatitis without necrosis or infection",
                                      "Primary sclerosing cholangitis"])
    assert "cholangitis" not in f and "infection" not in f
    assert derive_facts("pancreatitis", ["Acute pancreatitis", "Primary biliary cholangitis"]).get("cholangitis") is None


def test_diverticulitis_alarm_symptoms_need_explicit_presence():
    no_hem = derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)"])
    assert "alarm_symptoms" not in no_hem                                    # confirmed bug: used to be True
    assert "alarm_symptoms" not in derive_facts("diverticulitis", ["Diverticulitis of large intestine without perforation or abscess without bleeding"])
    assert derive_facts("diverticulitis", ["Diverticulitis of colon with hemorrhage"])["alarm_symptoms"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of large intestine without perforation or abscess with bleeding"])["alarm_symptoms"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)", "Iron deficiency anemia"])["alarm_symptoms"] is True


def test_diverticulitis_complicated_present_absent_unknown():
    assert derive_facts("diverticulitis", ["Diverticulitis of large intestine with perforation and abscess without bleeding"])["complicated"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)", "Peritonitis (acute) generalized"])["complicated"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)", "Generalized (acute) peritonitis"])["complicated"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)", "Perforation of intestine"])["complicated"] is True
    assert derive_facts("diverticulitis", ["Diverticulitis of large intestine without perforation or abscess without bleeding"])["complicated"] is False
    assert "complicated" not in derive_facts("diverticulitis", ["Diverticulitis of colon (without mention of hemorrhage)"])   # ICD-9: unknown


def test_unrelated_entries_do_not_leak_between_conditions():
    assert derive_facts("appendicitis", ["Acute pancreatitis with infected necrosis"]) == {}
    assert derive_facts("pancreatitis", ["Acute appendicitis with generalized peritonitis"]) == {}
    assert derive_facts("cholecystitis", ["Acute cholecystitis"]) == {}


def test_facts_the_record_cannot_support_are_never_derived():
    for diagnosis, titles in [("appendicitis", ["Acute appendicitis with peritoneal abscess"]),
                              ("pancreatitis", ["Biliary acute pancreatitis with infected necrosis"]),
                              ("diverticulitis", ["Diverticulitis of large intestine with perforation and abscess"])]:
        assert not set(derive_facts(diagnosis, titles)) & set(NOT_DERIVABLE)


def test_discharge_text_can_add_a_written_complication_but_never_rule_one_out():
    unspecified = ["Unspecified acute appendicitis"]
    assert derive_facts("appendicitis", unspecified, "Perforated appendicitis") == {"complicated": True}
    assert derive_facts("appendicitis", unspecified, "Gangrenous appendicitis with abscess") == {"complicated": True}
    assert derive_facts("appendicitis", unspecified, "Ruptured appendicitis") == {"complicated": True}
    assert derive_facts("appendicitis", unspecified, "Acute appendicitis") == {}                      # nothing written: unknown
    assert derive_facts("appendicitis", unspecified, "Appendicitis, no evidence of perforation") == {}  # negated: not a positive
    assert derive_facts("appendicitis", unspecified, "Appendicitis without perforation") == {}          # never False from text
    div = ["Diverticulitis of colon (without mention of hemorrhage)"]
    assert derive_facts("diverticulitis", div, "Perforated diverticulitis with abscess")["complicated"] is True
    assert "complicated" not in derive_facts("diverticulitis", div, "Acute diverticulitis")


def test_discharge_text_needs_the_disease_a_current_complication_and_no_negation():
    unspecified = ["Unspecified acute appendicitis"]
    assert derive_facts("appendicitis", unspecified, "Appendicitis; history of perforated peptic ulcer") == {}      # other disease
    assert derive_facts("appendicitis", unspecified, "Appendicitis, history of perforated appendicitis") == {}       # historical
    assert derive_facts("appendicitis", unspecified, "Perforated appendicitis") == {"complicated": True}
    div = ["Diverticulitis of colon (without mention of hemorrhage)"]
    assert "complicated" not in derive_facts("diverticulitis", div, "Diverticulitis, no evidence of peritonitis")
    assert "complicated" not in derive_facts("diverticulitis", div, "Diverticulitis without abscess or perforation")
    assert "complicated" not in derive_facts("diverticulitis", div, "Diverticulitis; perforated gastric ulcer")
    assert derive_facts("diverticulitis", div, "Acute diverticulitis with colovesical fistula")["complicated"] is True


def test_diverticulitis_fistula_and_bowel_habit_change():
    no_perf = "Diverticulitis of large intestine without perforation or abscess without bleeding"
    assert derive_facts("diverticulitis", [no_perf])["complicated"] is False
    assert derive_facts("diverticulitis", [no_perf, "Colovesical fistula"])["complicated"] is True     # not "uncomplicated"
    assert derive_facts("diverticulitis", [no_perf, "Stricture of colon"])["complicated"] is True
    assert derive_facts("diverticulitis", [no_perf, "Change in bowel habits"])["alarm_symptoms"] is True
    assert "alarm_symptoms" not in derive_facts("diverticulitis", [no_perf, "Abdominal pain, unspecified site"])


def test_discharge_text_false_positives_found_in_review_round_3():
    u = ["Unspecified acute appendicitis"]
    for text in ["Non-perforated appendicitis", "Appendicitis with abscess ruled out", "Appendicitis and perforated gastric ulcer",
                 "Appendicitis without abscess, perforation or gangrene", "Appendicitis, no evidence of perforation",
                 "Appendicitis; perforated duodenal ulcer", "Unperforated appendicitis", "Appendicitis, perforation excluded"]:
        assert derive_facts("appendicitis", u, text) == {}, text
    for text in ["Perforated appendicitis", "Ruptured appendix", "Appendicitis complicated by perforation",
                 "Gangrenous appendicitis with abscess"]:
        assert derive_facts("appendicitis", u, text) == {"complicated": True}, text
    div = ["Diverticulitis of colon (without mention of hemorrhage)"]
    for text in ["Diverticulitis with abscess ruled out", "Non-perforated diverticulitis", "Diverticulitis; perforated gastric ulcer",
                 "Diverticulitis without abscess, perforation or fistula"]:
        assert "complicated" not in derive_facts("diverticulitis", div, text), text
    assert derive_facts("diverticulitis", div, "Diverticulitis with pericolic abscess")["complicated"] is True
