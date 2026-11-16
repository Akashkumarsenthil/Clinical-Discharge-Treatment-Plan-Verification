"""G-Eval unit checks; no Ollama and no real clinical notes required."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.eval import geval as G  # noqa: E402


def test_batch_score_omits_case_context_from_returned_rows(monkeypatch):
    def fake_score(plan_text, case_context, judge_model="llama3.1:8b", timeout=60):
        assert "PRIVATE_NOTE" in case_context  # still used in memory
        return G.GEvalResult(
            scores={"coherence": 4, "relevance": 4, "fluency": 4, "groundedness": 4},
            composite=4.0,
            judge_model=judge_model,
        )

    monkeypatch.setattr(G, "score_plan", fake_score)
    rows = G.batch_score(
        [{"case_id": 101, "plan_text": "Diagnosis: appendicitis", "case_context": "PRIVATE_NOTE"}],
        judge_model="llama3.1:8b",
    )
    assert len(rows) == 1
    assert rows[0]["case_id"] == 101
    assert rows[0]["geval_composite"] == 4.0
    assert "case_context" not in rows[0]
    assert "PRIVATE_NOTE" not in str(rows)


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


def _ok_response():
    import json
    return _Resp(json.dumps({"message": {"content": "4"}}).encode())


def test_call_ollama_retries_while_ollama_restarts(monkeypatch):
    import urllib.error
    calls, sleeps = [], []

    def fake_urlopen(req, timeout):
        calls.append(1)
        if len(calls) <= 2:
            raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
        return _ok_response()

    monkeypatch.setattr(G.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(G.time, "sleep", sleeps.append)
    assert G._call_ollama("prompt", "judge") == "4"
    assert len(calls) == 3
    assert sleeps == list(G.RETRY_DELAYS[:2])


def test_call_ollama_gives_up_after_all_retries(monkeypatch):
    import urllib.error

    import pytest

    def refused(req, timeout):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    sleeps = []
    monkeypatch.setattr(G.urllib.request, "urlopen", refused)
    monkeypatch.setattr(G.time, "sleep", sleeps.append)
    with pytest.raises(urllib.error.URLError):
        G._call_ollama("prompt", "judge")
    assert sleeps == list(G.RETRY_DELAYS)


def test_call_ollama_does_not_retry_timeouts(monkeypatch):
    import socket

    import pytest

    calls = []

    def slow(req, timeout):
        calls.append(1)
        raise socket.timeout("timed out")

    monkeypatch.setattr(G.urllib.request, "urlopen", slow)
    monkeypatch.setattr(G.time, "sleep", lambda s: None)
    with pytest.raises(OSError):
        G._call_ollama("prompt", "judge")
    assert len(calls) == 1


def test_summarise_reports_unscored_plans():
    scored = {"geval_composite": 4.0, "geval_scores": {c: 4 for c in G.CRITERIA}}
    failed = {"geval_composite": 0.0, "geval_scores": {c: 0 for c in G.CRITERIA}}
    s = G.summarise([scored, failed, failed])
    assert s["n"] == 1 and s["n_unscored"] == 2 and s["mean"] == 4.0
    assert G.summarise([failed]) == {"n": 0, "n_unscored": 1, "mean": None, "min": None, "max": None}
