"""Summary counts fact-review rows, not distinct patients; uses human answers only."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import summarize_audit


def test_summary_counts_rows_and_does_not_use_model_suggestions(tmp_path, monkeypatch, capsys):
    (tmp_path / "results").mkdir()
    (tmp_path / "docs").mkdir()
    fields = ["hadm_id", "pathology", "fact", "derived_value", "evidence_source",
              summarize_audit.ANSWER, "ai_suggestion"]
    rows = [
        [1, "pancreatitis", "biliary", "unknown", "none", "yes", "no"],
        [1, "pancreatitis", "infection", "unknown", "none", "unsure", "yes"],
        [2, "pancreatitis", "infection", "unknown", "none", "", "yes"],
    ]
    with (tmp_path / "results/audit_sample.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(fields)
        writer.writerows(rows)
    monkeypatch.setattr(summarize_audit, "ROOT", tmp_path)
    assert summarize_audit.main() == 0
    output = capsys.readouterr().out
    assert "2 of 3 audit rows reviewed" in output
    assert "sampled cases reviewed" not in output
    with (tmp_path / "docs/case_facts_validation.csv").open() as fh:
        summary = list(csv.DictReader(fh))
    assert sum(int(row["yes"]) for row in summary) == 1
    assert sum(int(row["unsure"]) for row in summary) == 1
    assert sum(int(row["pending"]) for row in summary) == 1
