"""G-Eval: LLM-as-judge metric for discharge/treatment plan quality (professor requirement).

A judge LLM (default: llama3.1:8b via local Ollama) scores each generated plan on 4 criteria
using a 1–5 Likert scale. Scores are averaged into a composite G-Eval score.

Criteria (from G-Eval paper, adapted for clinical plans):
  1. Coherence      — plan is internally consistent and well-organised
  2. Relevance      — plan addresses the patient's diagnosis and presentation
  3. Fluency        — plan is grammatically and medically well-phrased
  4. Groundedness   — plan is grounded in the clinical notes (no hallucinated facts)

Usage:
    from clinverify.eval.geval import score_plan, batch_score
    result = score_plan(plan_text, case_context, judge_model="llama3.1:8b")
    print(result["composite"])   # float 1–5

Note: MIMIC text must NOT be sent to any hosted API. This module uses local Ollama only.
"""
from __future__ import annotations

import json
import os
import http.client
import statistics
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


DEFAULT_JUDGE_MODEL = "llama3.1:8b"


def ollama_chat_url() -> str:
    """Local Ollama chat endpoint. OLLAMA_HOST may point at this machine or the Docker host only (tests use a stub)."""
    from clinverify.models.model_a import local_ollama_host
    return local_ollama_host(os.environ.get("OLLAMA_HOST", "http://localhost:11434")) + "/api/chat"

CRITERIA = {
    "coherence": (
        "Is the discharge and treatment plan internally consistent, well-structured, "
        "and logically organised? Score 1 (incoherent) to 5 (perfectly coherent)."
    ),
    "relevance": (
        "Does the plan directly address the patient's diagnosis and clinical presentation "
        "as described in the clinical notes? Score 1 (irrelevant) to 5 (fully relevant)."
    ),
    "fluency": (
        "Is the plan grammatically correct and written in appropriate clinical language? "
        "Score 1 (poor) to 5 (excellent)."
    ),
    "groundedness": (
        "Are all clinical details in the plan supported by the clinical notes provided? "
        "Penalise hallucinated findings, lab values, or diagnoses not in the notes. "
        "Score 1 (heavily hallucinated) to 5 (fully grounded)."
    ),
}

SCORE_PROMPT = """You are evaluating a clinical discharge and treatment plan.

[Clinical notes]
{context}

[Plan to evaluate]
{plan}

[Task]
{criterion}

Respond with ONLY a single integer from 1 to 5. No explanation."""


@dataclass
class GEvalResult:
    scores: dict[str, int] = field(default_factory=dict)
    composite: float = 0.0
    judge_model: str = DEFAULT_JUDGE_MODEL
    error: Optional[str] = None


# Seconds to wait before each retry when Ollama refuses or drops the connection. systemd restarts a crashed Ollama
# within a few seconds; without retries every remaining plan in the batch fails at once (2026-11-15: 398 of 460).
RETRY_DELAYS = (2, 4, 8, 16, 30)


def _is_connection_failure(exc: BaseException) -> bool:
    """Server not reachable (refused, reset, dropped). Timeouts and HTTP errors are not retried."""
    if isinstance(exc, urllib.error.HTTPError):
        return False
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    return isinstance(reason, (ConnectionError, http.client.RemoteDisconnected))


def _call_ollama(prompt: str, model: str, timeout: int = 60) -> str:
    for delay in (*RETRY_DELAYS, None):
        try:
            return _call_ollama_once(prompt, model, timeout)
        except (urllib.error.URLError, ConnectionError, http.client.RemoteDisconnected) as exc:
            if delay is None or not _is_connection_failure(exc):
                raise
            time.sleep(delay)
    raise AssertionError("unreachable")


def _call_ollama_once(prompt: str, model: str, timeout: int) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 4},
    }).encode()
    req = urllib.request.Request(
        ollama_chat_url(), data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"].strip()


def _parse_score(text: str) -> Optional[int]:
    for ch in text:
        if ch.isdigit():
            v = int(ch)
            if 1 <= v <= 5:
                return v
    return None


def score_plan(
    plan_text: str,
    case_context: str,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    timeout: int = 60,
) -> GEvalResult:
    """Score one plan against all four criteria. Returns GEvalResult."""
    result = GEvalResult(judge_model=judge_model)
    for crit_name, crit_desc in CRITERIA.items():
        prompt = SCORE_PROMPT.format(
            context=case_context[:3000],  # keep prompt short
            plan=plan_text[:2000],
            criterion=crit_desc,
        )
        try:
            raw = _call_ollama(prompt, judge_model, timeout)
            score = _parse_score(raw)
            if score is None:
                result.error = f"Unparseable score for {crit_name}: {raw!r}"
                score = 3  # neutral fallback
            result.scores[crit_name] = score
        except (urllib.error.URLError, OSError, KeyError) as exc:
            result.error = str(exc)
            result.scores[crit_name] = 0

    valid = [s for s in result.scores.values() if s > 0]
    result.composite = round(statistics.mean(valid), 3) if valid else 0.0
    return result


def batch_score(
    plans: list[dict],
    judge_model: str = DEFAULT_JUDGE_MODEL,
    timeout: int = 60,
) -> list[dict]:
    """Score a list of plan dicts. Each dict must have 'plan_text' and 'case_context'.

    Uses case_context only in memory for the judge call. Returned / saved rows never
    include case_context (MIMIC notes stay off disk in results JSON).
    """
    out = []
    for item in plans:
        res = score_plan(
            item["plan_text"], item.get("case_context", ""),
            judge_model=judge_model, timeout=timeout,
        )
        row = {
            "plan_text": item.get("plan_text"),
            "geval_scores": res.scores,
            "geval_composite": res.composite,
            "geval_error": res.error,
        }
        if "case_id" in item:
            row["case_id"] = item["case_id"]
        out.append(row)
    return out


def summarise(results: list[dict]) -> dict:
    """Aggregate geval_composite scores from batch_score output.

    n counts scored plans only; n_unscored counts plans where every judge call failed (composite 0). Report both:
    a mean over the scored plans alone hides how many were never judged.
    """
    composites = [r["geval_composite"] for r in results if r.get("geval_composite")]
    unscored = len(results) - len(composites)
    if not composites:
        return {"n": 0, "n_unscored": unscored, "mean": None, "min": None, "max": None}
    return {
        "n": len(composites),
        "n_unscored": unscored,
        "mean": round(statistics.mean(composites), 3),
        "min": round(min(composites), 3),
        "max": round(max(composites), 3),
        "per_criterion": {
            crit: round(statistics.mean(
                r["geval_scores"].get(crit, 0) for r in results
                if r.get("geval_scores", {}).get(crit)
            ), 3)
            for crit in CRITERIA
        },
    }
