"""Live prototype: pick a validation case, get Model A's plan, and see the Z3 verifier accept it or name the broken rule.

Run from the repository root (data in MIMIC_DIR, default ~/data/mimic):
    pip install -r requirements.txt
    streamlit run app/demo_app.py

Patient text stays on this machine and is hidden unless the sidebar switch is turned on. Only the validation split is
offered: the 100 test cases are held out for the formal evaluation. The plan can be edited, so the audience can try to
break a rule; "Inject a fault" finds a small edit that does it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data.case_loader import load_case_facts, plan_from_model_output  # noqa: E402
from clinverify.eval.protocol import cohort_ids  # noqa: E402
from clinverify.models import model_a as A  # noqa: E402
from clinverify.plan import DIAGNOSES, TREATMENT_CONCEPTS  # noqa: E402
from clinverify.rules.catalog import CATALOG_VERSION, catalog  # noqa: E402
from clinverify.verifier.z3_verifier import verify  # noqa: E402

SAVED_PLANS = ROOT / "results" / "model_runs" / "model_a_qwen2.5_14b_val_seed298.jsonl"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
DAYS_TRIED = (0, 3, 7, 14)


@st.cache_data(show_spinner="Reading case facts from the local record...")
def facts_for_validation() -> dict[int, dict]:
    return load_case_facts(cohort_ids("validation"))


@st.cache_data
def saved_plans() -> dict[int, dict]:
    if not SAVED_PLANS.exists():
        return {}
    return {p["case_id"]: p for p in A.load_plans(SAVED_PLANS)}


@st.cache_resource(show_spinner="Loading the record tables for live generation...")
def model_inputs() -> dict[int, str]:
    from clinverify.data import ext_cdm as E

    cleaned, _ = E.clean_tables(E.load_tables())
    cleaned.pop("lab_test_mapping", None)
    return A.case_inputs(E.transform_tables(cleaned), cohort_ids("validation"))


def live_plan(case_id: int) -> dict:
    client = A.Ollama(OLLAMA_MODEL, timeout=300)
    client.digest()                                     # raises if the server or model is missing
    resp = client.chat(A.SYSTEM_PROMPT, A.USER_TEMPLATE.format(case_id=case_id, record=model_inputs()[case_id]),
                       seed=298, temperature=0.0, top_p=1.0, max_new_tokens=256, num_ctx=8192, schema=A.PLAN_SCHEMA)
    return A.parse_plan(case_id, resp["message"]["content"])


def check(plan_dict: dict, facts: dict):
    plan = plan_from_model_output(plan_dict, facts)
    return plan, verify(plan, list(catalog))


def rule_table(plan, result) -> pd.DataFrame:
    rows = []
    for rule in catalog:
        if rule.id in result.violated:
            status = "ADVISORY violation" if rule.id in result.advisory else "VIOLATED"
            detail = result.messages.get(rule.id, "")
        elif rule.id in result.inconclusive:
            needed = rule.requires_for(plan) if rule.requires_for else rule.requires
            status = "unknown (advisory)" if rule.id in result.advisory_inconclusive else "unknown"
            detail = "record does not establish: " + ", ".join(n.removeprefix("facts.") for n in needed if not plan.has(n))
        elif rule.id in result.not_applicable:
            status, detail = "not applicable", rule.applies_when
        else:
            status, detail = "passed", rule.description
        rows.append({"rule": rule.id, "name": rule.name, "status": status, "detail": detail, "source": rule.source})
    order = {"VIOLATED": 0, "ADVISORY violation": 1, "unknown": 2, "unknown (advisory)": 3, "passed": 4, "not applicable": 5}
    return pd.DataFrame(rows).sort_values("status", key=lambda s: s.map(order), kind="stable").reset_index(drop=True)


def find_breaking_edit(plan_dict: dict, facts: dict):
    """The smallest edit (drop or add one treatment, or change the post-op antibiotic days) that makes a blocking rule fail."""
    base = plan_dict["treatments"]
    candidates = [{**plan_dict, "treatments": [t for t in base if t != drop]} for drop in base]
    candidates += [{**plan_dict, "treatments": base + [add]} for add in TREATMENT_CONCEPTS if add not in base]
    candidates += [{**plan_dict, "postop_antibiotic_days": d} for d in DAYS_TRIED if d != plan_dict["postop_antibiotic_days"]]
    for cand in candidates:
        try:
            _, res = check(cand, facts)
        except ValueError:
            continue
        if res.blocking:
            return cand, res
    return None, None


@st.cache_data
def demo_shortcuts(_facts: dict) -> dict[str, int]:
    """One saved-plan case per kind of outcome, so a live demo can jump to each. Chosen by rule, not by hand."""
    found: dict[str, int] = {}
    for h, p in sorted(saved_plans().items()):
        if h not in _facts:
            continue
        _, res = check(p, _facts)
        right = p["diagnosis"] == _facts[h]["pathology"]
        if res.status == "valid" and right:
            found.setdefault("Accepted: correct diagnosis, plan passes the checks", h)
        elif res.blocking and not right and "R-GEN-001" not in res.blocking:
            found.setdefault("Rejected: wrong diagnosis caught by a rule", h)
        elif res.blocking and right and "R-GEN-001" not in res.blocking:
            found.setdefault("Rejected: correct diagnosis, a clinical rule broken", h)
        elif res.status == "insufficient_information" and right:
            found.setdefault("Not accepted: the record lacks a fact a rule needs", h)
        elif "R-GEN-001" in res.blocking:
            found.setdefault("Out of scope: cholecystitis (no treatment rules yet)", h)
    return found


def edit_summary(before: dict, after: dict) -> str:
    gone = [t for t in before["treatments"] if t not in after["treatments"]]
    new = [t for t in after["treatments"] if t not in before["treatments"]]
    parts = [f"removed {t}" for t in gone] + [f"added {t}" for t in new]
    if before["postop_antibiotic_days"] != after["postop_antibiotic_days"]:
        parts.append(f"post-op antibiotic days {before['postop_antibiotic_days']} -> {after['postop_antibiotic_days']}")
    return ", ".join(parts)


st.set_page_config(page_title="Plan verifier demo", layout="wide")
st.title("Neurosymbolic verification of an LLM-drafted care plan")
st.caption(f"Team 6 · DATA 298A · rule catalog v{CATALOG_VERSION} ({len(list(catalog))} rules, written by the team) · Z3 solver. "
           "Experimental research prototype, not clinical decision support. \"Valid\" means the plan complies with our formal rules.")

try:
    facts = facts_for_validation()
except Exception as err:  # data missing on this machine
    st.error(f"Case facts could not be read from the local record ({type(err).__name__}). Set MIMIC_DIR to the folder that "
             "holds mimic-iv-ext-cdm-1.1, or use the synthetic data (README, Quickstart).")
    st.stop()

with st.sidebar:
    st.header("Case")
    pathology = st.selectbox("Pathology", ["all", *DIAGNOSES])
    shortcuts = demo_shortcuts(facts)
    pick = st.selectbox("Demo shortcut", ["(choose a case below)", *shortcuts])
    ids = [h for h, c in sorted(facts.items()) if pathology in ("all", c["pathology"])]
    case_id = shortcuts[pick] if pick in shortcuts else st.selectbox("Case (hadm_id)", ids)
    source = st.radio("Plan source", ["Saved Model A plan", "Generate live with Model A"],
                      help=f"Live generation needs a local Ollama server with {OLLAMA_MODEL}. Nothing leaves this machine.")
    show_text = st.toggle("Show patient text (authorised machine only)", value=False)
    st.caption("Only the validation split is offered. The 100 test cases are held out.")

case = facts[case_id]
st.subheader(f"Case {case_id} · reference pathology: {case['pathology']}")
left, right = st.columns([1, 2])

with left:
    st.markdown("**Facts taken from the record** (never shown to the model)")
    st.dataframe(pd.DataFrame([{"fact": k, "value": {True: "yes", False: "no", None: "unknown"}[v]}
                               for k, v in sorted(case["facts"].items())]), hide_index=True, width="stretch")
    if show_text:
        try:
            st.text_area("Model input", model_inputs()[case_id], height=300)
        except Exception as err:
            st.warning(f"Patient text unavailable ({type(err).__name__}).")

state_key = f"plan_{case_id}_{source}"
if state_key not in st.session_state:
    st.session_state[state_key] = None
    st.session_state["note"] = ""

with right:
    st.markdown("**Model A's plan**")
    if st.session_state[state_key] is None:
        if source == "Saved Model A plan":
            st.session_state[state_key] = saved_plans().get(case_id)
            if st.session_state[state_key] is None:
                st.warning("No saved plan for this case (it counts as a missing output in the evaluation).")
        elif st.button("Generate plan now"):
            try:
                with st.spinner("Model A is writing a plan on the local GPU..."):
                    st.session_state[state_key] = live_plan(case_id)
            except Exception as err:
                st.error(f"Live generation failed ({type(err).__name__}: {err}). Switch to the saved plan.")
    base = st.session_state[state_key]
    if base is None:
        st.stop()

    c1, c2, c3 = st.columns(3)
    diagnosis = c1.selectbox("Diagnosis", list(DIAGNOSES), index=list(DIAGNOSES).index(base["diagnosis"]), key=f"dx{state_key}")
    days = c3.selectbox("Post-op antibiotic days", [None, 0, 1, 2, 3, 4, 5, 7, 10, 14], key=f"d{state_key}",
                        index=[None, 0, 1, 2, 3, 4, 5, 7, 10, 14].index(base["postop_antibiotic_days"])
                        if base["postop_antibiotic_days"] in [None, 0, 1, 2, 3, 4, 5, 7, 10, 14] else 0)
    treatments = c2.multiselect("Treatments", list(TREATMENT_CONCEPTS), default=base["treatments"], key=f"t{state_key}")
    plan_dict = {"case_id": case_id, "diagnosis": diagnosis, "treatments": treatments, "postop_antibiotic_days": days}

    if st.button("Inject a fault (find an edit that breaks a rule)"):
        edit, _ = find_breaking_edit(plan_dict, facts)
        if edit is None:
            st.info("No single edit breaks a blocking rule for this case. Try another case.")
        else:
            st.session_state["note"] = f"Fault injected: {edit_summary(plan_dict, edit)}. Turn on the switch below to verify the faulty plan."
            st.session_state["faulty"] = edit
    if st.session_state.get("note"):
        st.info(st.session_state["note"])

    shown = st.session_state.get("faulty") if st.session_state.get("faulty", {}).get("case_id") == case_id and \
        st.toggle("Verify the fault-injected plan instead", value=False) else plan_dict

    plan, result = check(shown, facts)
    verdict = {"valid": ("success", "ACCEPTED: no blocking rule is violated and every applicable check could be decided."),
               "violated": ("error", "REJECTED: " + ", ".join(result.blocking) + " broken."),
               "insufficient_information": ("warning", "NOT ACCEPTED: the record does not establish a fact a blocking rule needs, "
                                            "so the plan cannot be called valid. " + ", ".join(result.blocking_inconclusive))}[result.status]
    getattr(st, verdict[0])(verdict[1])
    truth_ok = shown["diagnosis"] == case["pathology"]
    st.caption(f"Diagnosis vs reference: {'correct' if truth_ok else 'WRONG'} · solver time {result.solve_ms:.1f} ms · "
               f"{len(result.violated)} violated, {len(result.inconclusive)} unknown, {len(result.not_applicable)} not applicable")

    for rid, msg in result.messages.items():
        st.markdown(f"- **{rid}**: {msg}")
    st.dataframe(rule_table(plan, result), hide_index=True, width="stretch")
    st.download_button("Download this verdict (case ID and rule IDs only)",
                       json.dumps({"case_id": case_id, "plan": shown, "status": result.status, "violated": result.violated,
                                   "inconclusive": result.inconclusive, "catalog": CATALOG_VERSION}, indent=1),
                       file_name=f"verdict_{case_id}.json")
