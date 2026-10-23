"""Audit triage is not human sign-off; test safeguards with synthetic evidence."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from triage_audit import quote_exists, quote_policy_check, triage_category


def test_quote_must_exist_in_the_specified_evidence_field():
    sample = {"icd_titles": "Acute pancreatitis without necrosis or infection", "discharge_diagnosis": "Acute pancreatitis"}
    assert quote_exists({"evidence_field": "icd_titles", "evidence_quote": "without necrosis or infection"}, sample)
    assert not quote_exists({"evidence_field": "discharge_diagnosis", "evidence_quote": "without necrosis or infection"}, sample)
    assert not quote_exists({"evidence_field": "icd_titles", "evidence_quote": "with infected necrosis"}, sample)
    assert not quote_exists({"evidence_field": "icd_titles", "evidence_quote": "no"}, sample)


def test_local_model_opinions_never_become_confirmed_fixes_or_manual_reviews():
    answer = {"supported_value": "true", "needs_domain_review": False}
    assert triage_category("unknown", answer, True) == "evidence_candidate_for_human_review"
    assert triage_category("true", answer, True) == "second_opinion_matches_extractor"
    assert triage_category("unknown", answer, False) == "no_verified_support_for_second_opinion"
    answer["needs_domain_review"] = True
    assert triage_category("unknown", answer, True) == "domain_review_required"
    answer = {"supported_value": "unknown", "needs_domain_review": False}
    assert triage_category("unknown", answer, False) == "conservative_unknown_retained"


def test_a_real_quotation_is_not_necessarily_support_for_the_claim():
    title = "Diverticulitis of large intestine with perforation and abscess without bleeding"
    assert quote_policy_check("alarm_symptoms", "true", title) == "bleeding_negative_title_does_not_decide_all_alarm_symptoms"
    assert quote_policy_check("alarm_symptoms", "false", title) == "bleeding_negative_title_does_not_decide_all_alarm_symptoms"
    assert quote_policy_check("biliary", "false", "Acute pancreatitis") == "generic_diagnosis_does_not_establish_requested_fact"
    assert quote_policy_check("necrotizing", "false", "Acute pancreatitis with uninfected necrosis") == "quoted_positive_necrosis_conflicts_with_claim"
    assert quote_policy_check("necrotizing", "true", "Acute pancreatitis without necrosis or infection") == "quoted_negative_necrosis_conflicts_with_claim"
    assert quote_policy_check("necrotizing", "false", "Acute pancreatitis without necrosis or infection") == "not_adjudicated_by_spot_checks"
