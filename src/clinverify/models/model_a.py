"""Model A: a local LLM writes the diagnosis and treatment plan directly (docs/model_a_plan_format.md).

Full-information setting: the model gets the history, the exam, the labs, microbiology and radiology for a case at once
(Hager et al. 2024 also report this setting next to the autonomous one; our numbers are not their autonomous 54.9%).
The model never sees the discharge diagnosis, ICD codes or procedures (they give the answer away), and it never sees the
case facts or the rules: the facts are used only to judge the plan.

MIMIC text must not go to a hosted API, so generation runs on a local Ollama server (default http://localhost:11434).
Output is constrained to the plan JSON schema; anything that still fails to parse is left out and counted as a missing
output by the fixed-cohort scorer, never retried for a better answer.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from clinverify.plan import DIAGNOSES, TREATMENT_CONCEPTS

MAX_LABS = 40                 # abnormal results first, then the rest, up to this many rows
MAX_RADIOLOGY = 3             # reports per case
MAX_REPORT_CHARS = 1500       # per radiology report
MAX_MICRO = 15

SYSTEM_PROMPT = """You are a hospital physician. You are given one patient's admission record: history of present illness,
physical examination, laboratory results, microbiology and imaging. Decide the most likely diagnosis and the treatment plan
for this admission.

Answer with JSON only, using exactly these fields:
  diagnosis: one of appendicitis, cholecystitis, diverticulitis, pancreatitis
  treatments: the treatments you would order, as a list chosen from
    antibiotics                       an antibiotic treatment course (not a single surgical prophylaxis dose)
    preoperative_antibiotic           a single antibiotic dose before surgery as prophylaxis
    appendectomy                      surgical removal of the appendix
    cholecystectomy_during_admission  gallbladder removal before discharge
    ercp                              endoscopic retrograde cholangiopancreatography
    parenteral_nutrition              intravenous nutrition
    colonoscopy_after_recovery        a colonoscopy planned after the acute illness
    (an empty list means none of these)
  postop_antibiotic_days: whole days of antibiotics after surgery, 0 if none, null if no surgery is planned"""

USER_TEMPLATE = "Patient record (case {case_id}):\n\n{record}\n\nReturn the JSON plan."

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis": {"type": "string", "enum": list(DIAGNOSES)},
        "treatments": {"type": "array", "items": {"type": "string", "enum": list(TREATMENT_CONCEPTS)}, "uniqueItems": True},
        "postop_antibiotic_days": {"type": ["integer", "null"], "minimum": 0},
    },
    "required": ["diagnosis", "treatments", "postop_antibiotic_days"],
    "additionalProperties": False,
}


def prompt_sha256() -> str:
    """Hash of everything fixed in the prompt (system text, template, schema, input limits). Goes in the run metadata."""
    fixed = json.dumps({"system": SYSTEM_PROMPT, "user": USER_TEMPLATE, "schema": PLAN_SCHEMA,
                        "limits": [MAX_LABS, MAX_RADIOLOGY, MAX_REPORT_CHARS, MAX_MICRO]}, sort_keys=True)
    return hashlib.sha256(fixed.encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ case input
def _lab_lines(labs: pd.DataFrame) -> list[str]:
    labs = labs.assign(_abn=labs["flag"].isin(["low", "high"])).sort_values("_abn", ascending=False, kind="stable")
    lines = []
    for _, r in labs.head(MAX_LABS).iterrows():
        name = r["label"] if isinstance(r.get("label"), str) else f"item {r['itemid']}"
        flag = f" [{r['flag']}]" if r["flag"] in ("low", "high") else ""
        lines.append(f"- {name}: {r['valuestr']}{flag}")
    return lines


def case_inputs(transformed: dict[str, pd.DataFrame], hadm_ids: Optional[Iterable[int]] = None) -> dict[int, str]:
    """{hadm_id: record text} from the transformed Ext-CDM tables. Leaves out discharge diagnosis, ICD and procedures."""
    hpi = transformed["history_of_present_illness"].set_index("hadm_id")["hpi"]
    pe = transformed["physical_examination"].set_index("hadm_id")["pe"]
    labs = dict(tuple(transformed["laboratory_tests"].groupby("hadm_id")))
    micro = dict(tuple(transformed["microbiology"].groupby("hadm_id")))
    rad = dict(tuple(transformed["radiology_reports"].groupby("hadm_id")))
    ids = hpi.index if hadm_ids is None else [int(h) for h in hadm_ids]
    out = {}
    for h in ids:
        parts = [f"HISTORY OF PRESENT ILLNESS\n{hpi.get(h, '')}", f"PHYSICAL EXAMINATION\n{pe.get(h, '')}"]
        if h in labs:
            parts.append("LABORATORY RESULTS\n" + "\n".join(_lab_lines(labs[h])))
        if h in micro:
            parts.append("MICROBIOLOGY\n" + "\n".join(f"- {v}" for v in micro[h]["valuestr"].astype(str).head(MAX_MICRO)))
        if h in rad:
            reports = [f"{r['modality']} {r['region']} ({r['exam_name']}): {str(r['text'])[:MAX_REPORT_CHARS]}"
                       for _, r in rad[h].head(MAX_RADIOLOGY).iterrows()]
            parts.append("IMAGING\n" + "\n".join(reports))
        out[int(h)] = "\n\n".join(parts)
    return out


# ------------------------------------------------------------------------------------------------ Ollama client
class Ollama:
    """Minimal client for a local Ollama server (stdlib only)."""

    def __init__(self, model: str, host: Optional[str] = None, timeout: int = 600):
        self.model = model
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.timeout = timeout

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.host + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def models(self) -> list[dict]:
        with urllib.request.urlopen(self.host + "/api/tags", timeout=10) as resp:
            return json.loads(resp.read())["models"]

    def digest(self) -> str:
        for m in self.models():
            if m["name"] == self.model or m["model"] == self.model:
                return m["digest"]
        raise ValueError(f"model {self.model!r} is not pulled; run: ollama pull {self.model}")

    def chat(self, system: str, user: str, *, seed: int, temperature: float, top_p: float, max_new_tokens: int,
             num_ctx: int, schema: dict) -> dict:
        return self._post("/api/chat", {
            "model": self.model, "stream": False, "format": schema, "keep_alive": "30m",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"seed": seed, "temperature": temperature, "top_p": top_p, "num_predict": max_new_tokens, "num_ctx": num_ctx},
        })


def parse_plan(case_id: int, content: str) -> dict:
    """Model text -> plan dict in the verifier's format. Raises ValueError when it is not a usable plan."""
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    plan = {"case_id": int(case_id), "diagnosis": data.get("diagnosis"),
            "treatments": list(dict.fromkeys(data.get("treatments") or [])),
            "postop_antibiotic_days": data.get("postop_antibiotic_days")}
    if plan["diagnosis"] not in DIAGNOSES:
        raise ValueError("diagnosis outside the four benchmark pathologies")
    return plan


def generate_plans(client: Ollama, inputs: dict[int, str], case_ids: Iterable[int], out_jsonl: Path, *, seed: int = 298,
                   temperature: float = 0.0, top_p: float = 1.0, max_new_tokens: int = 256, num_ctx: int = 8192,
                   progress_every: int = 25) -> pd.DataFrame:
    """Generate one plan per case and append it to `out_jsonl` as it goes, so an interrupted run resumes where it stopped.
    One attempt per case: a generation that fails is logged and left out (the scorer counts it as missing).
    Returns a log frame with case_id, ok, error, seconds and token counts (no patient text)."""
    out_jsonl = Path(out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["case_id"] for l in out_jsonl.read_text().splitlines() if l.strip()} if out_jsonl.exists() else set()
    todo = [int(h) for h in case_ids if int(h) not in done]
    rows, t_start = [], time.perf_counter()
    with out_jsonl.open("a") as fh:
        for i, h in enumerate(todo, 1):
            t0 = time.perf_counter()
            row = {"case_id": h, "ok": False, "error": None}
            try:
                resp = client.chat(SYSTEM_PROMPT, USER_TEMPLATE.format(case_id=h, record=inputs[h]), seed=seed,
                                   temperature=temperature, top_p=top_p, max_new_tokens=max_new_tokens, num_ctx=num_ctx,
                                   schema=PLAN_SCHEMA)
                row.update(prompt_tokens=resp.get("prompt_eval_count"), output_tokens=resp.get("eval_count"))
                plan = parse_plan(h, resp["message"]["content"])
                fh.write(json.dumps({"case_id": h, "plan": plan}) + "\n")
                fh.flush()
                row["ok"] = True
            except (ValueError, KeyError, json.JSONDecodeError) as err:
                row["error"] = type(err).__name__        # message may quote model text; keep only the type
                fh.write(json.dumps({"case_id": h, "plan": None, "error": row["error"]}) + "\n")
                fh.flush()
            row["seconds"] = time.perf_counter() - t0
            rows.append(row)
            if progress_every and i % progress_every == 0:
                rate = (time.perf_counter() - t_start) / i
                print(f"{i}/{len(todo)} cases, {rate:.1f} s/case, about {rate * (len(todo) - i) / 60:.0f} min left")
    return pd.DataFrame(rows)


def load_plans(out_jsonl: Path) -> list[dict]:
    """Plans from a generation file, failed generations left out (they count as missing outputs)."""
    rows = [json.loads(l) for l in Path(out_jsonl).read_text().splitlines() if l.strip()]
    return [r["plan"] for r in rows if r.get("plan")]
