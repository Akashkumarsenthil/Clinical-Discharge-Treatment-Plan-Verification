"""Case-fact derivation from ICD titles (public title wording only, no patient data)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clinverify.data.case_facts import NOT_DERIVABLE, derive_facts  # noqa: E402


def test_appendicitis_complicated_only_with_peritonitis_or_abscess():
    assert derive_facts("appendicitis", ["Acute appendicitis with generalized peritonitis"]) == {"complicated": True}
    assert derive_facts("appendicitis", ["Acute appendicitis with peritoneal abscess"]) == {"complicated": True}
    assert derive_facts("appendicitis", ["Unspecified acute appendicitis"]) == {"complicated": False}


def test_pancreatitis_necrosis_infection_and_biliary():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis with infected necrosis without cholangitis"])
    assert f["necrotizing"] and f["infection"] and f["biliary"] and not f["mild"]
    g = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection"])
    assert g["biliary"] and g["mild"] and not g["necrotizing"] and not g["infection"]
    h = derive_facts("pancreatitis", ["Idiopathic acute pancreatitis with uninfected necrosis"])
    assert h["necrotizing"] and not h["infection"] and not h["biliary"]


def test_pancreatitis_cholangitis_and_obstruction_and_organ_failure():
    f = derive_facts("pancreatitis", ["Biliary acute pancreatitis without necrosis or infection",
                                      "Cholangitis, unspecified", "Obstruction of bile duct", "Acute kidney failure"])
    assert f["cholangitis"] and f["infection"] and f["biliary_obstruction"] and not f["mild"]


def test_diverticulitis_complicated_and_alarm_symptoms():
    complicated = ["Diverticulitis of large intestine with perforation and abscess without bleeding"]
    assert derive_facts("diverticulitis", complicated)["complicated"] is True
    simple = ["Diverticulitis of large intestine without perforation or abscess without bleeding"]
    f = derive_facts("diverticulitis", simple)
    assert f == {"complicated": False, "alarm_symptoms": False}
    assert derive_facts("diverticulitis", ["Diverticulitis of large intestine without perforation or abscess with bleeding"]
                        )["alarm_symptoms"] is True
    assert derive_facts("diverticulitis", simple + ["Iron deficiency anemia"])["alarm_symptoms"] is True


def test_unrelated_entries_do_not_leak_between_conditions():
    assert derive_facts("appendicitis", ["Acute pancreatitis with infected necrosis"]) == {}
    assert derive_facts("pancreatitis", ["Acute appendicitis with generalized peritonitis"]) == {}
    assert derive_facts("cholecystitis", ["Acute cholecystitis"]) == {}


def test_facts_the_record_cannot_support_are_never_derived():
    for diagnosis, titles in [("appendicitis", ["Acute appendicitis with peritoneal abscess"]),
                              ("pancreatitis", ["Biliary acute pancreatitis with infected necrosis"]),
                              ("diverticulitis", ["Diverticulitis of large intestine with perforation and abscess"])]:
        assert not set(derive_facts(diagnosis, titles)) & set(NOT_DERIVABLE)
