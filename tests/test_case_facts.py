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
    assert g["biliary"] is True and g["necrotizing"] is False and g["infection"] is False and g["mild"] is True
    h = derive_facts("pancreatitis", ["Idiopathic acute pancreatitis with uninfected necrosis"])
    assert h["necrotizing"] is True and h["biliary"] is False and h["mild"] is False
    assert "infection" not in h                      # uninfected necrosis does not rule out an infection elsewhere


def test_pancreatitis_infection_absent_only_when_none_coded():
    base = "Idiopathic acute pancreatitis without necrosis or infection"
    assert derive_facts("pancreatitis", [base])["infection"] is False
    assert "infection" not in derive_facts("pancreatitis", [base, "Pneumonia, unspecified organism"])


def test_pancreatitis_mild_is_false_for_organ_failure_and_unknown_without_explicit_title():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection", "Acute kidney failure"])
    assert f["mild"] is False
    assert "mild" not in derive_facts("pancreatitis", ["Acute pancreatitis", "Hypertension"])


def test_pancreatitis_cholangitis_and_obstruction():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection",
                                      "Cholangitis, unspecified", "Obstruction of bile duct"])
    assert f["cholangitis"] is True and f["infection"] is True and f["biliary_obstruction"] is True
    g = derive_facts("pancreatitis", ["Acute pancreatitis"])
    assert g["cholangitis"] is False and g["biliary_obstruction"] is False


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
