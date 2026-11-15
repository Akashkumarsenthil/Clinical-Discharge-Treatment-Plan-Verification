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
