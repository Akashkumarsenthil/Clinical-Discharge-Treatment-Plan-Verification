"""Generation CLI contract and guard checks; fake clients and invented IDs only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("generate_model_a_cli", ROOT / "scripts/generate_model_a_plans.py")
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

from clinverify.models import model_a as A  # noqa: E402
from clinverify.eval.protocol import validate_generation_metadata  # noqa: E402


@pytest.fixture
def frozen_root(tmp_path):
    """Tiny synthetic protocol: never reads the real test membership or records."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "results").mkdir()
    ids = [101, 102]
    protocol = {"generation_seeds": [298, 299, 300], "catalog_version": "2.1", "supported_test_cases": 2,
                "supported_test_ids_sha256": hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()}
    (tmp_path / "docs/evaluation_protocol.json").write_text(json.dumps(protocol))
    manifest = {"schema_version": 1, "catalog_version": "2.1", "reviewer": "synthetic-reviewer",
                "review_date": "2026-01-01", "blind_to_plans": True,
                "cases": [{"case_id": cid, "eligible": True, "reason": ""} for cid in ids]}
    (tmp_path / "results/eligibility_manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "docs/model_a_freeze_checklist.md").write_text("# Synthetic checklist\n- [x] fixture signed\n")
    return tmp_path


def no_real_generation(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("test touched the real cohort, patient data, or Ollama")
    monkeypatch.setattr(G, "cohort_ids", forbidden)
    monkeypatch.setattr(G, "local_inputs", forbidden)
    monkeypatch.setattr(A, "Ollama", forbidden)


def test_test_cohort_refuses_without_confirmation_before_any_io(frozen_root, monkeypatch, capsys):
    no_real_generation(monkeypatch)
    with pytest.raises(SystemExit) as result:
        G.main(["--cohort", "test"], root=frozen_root)
    assert result.value.code == 2
    assert "--i-confirm-freeze is required" in capsys.readouterr().err
    assert not (frozen_root / "results/model_runs").exists()


@pytest.mark.parametrize("contents", ["- [ ] pending\n", "| Item | [ ] |\n", "no boxes\n"])
def test_test_cohort_refuses_incomplete_checklist(frozen_root, monkeypatch, capsys, contents):
    no_real_generation(monkeypatch)
    (frozen_root / "docs/model_a_freeze_checklist.md").write_text(contents)
    with pytest.raises(SystemExit):
        G.main(["--cohort", "test", "--i-confirm-freeze", "--dry-run"], root=frozen_root)
    assert "checklist" in capsys.readouterr().err
    assert not (frozen_root / "results/model_runs").exists()


def test_test_cohort_refuses_missing_manifest(frozen_root, monkeypatch, capsys):
    no_real_generation(monkeypatch)
    (frozen_root / "results/eligibility_manifest.json").unlink()
    with pytest.raises(SystemExit):
        G.main(["--cohort", "test", "--i-confirm-freeze", "--dry-run"], root=frozen_root)
    assert "eligibility_manifest.json is missing" in capsys.readouterr().err


@pytest.mark.parametrize("value", [{}, {"cases": [{"case_id": 999}]}])
def test_placeholder_or_wrong_cohort_manifest_cannot_unlock_test(frozen_root, value):
    (frozen_root / "results/eligibility_manifest.json").write_text(json.dumps(value))
    with pytest.raises(G.ConfigurationError, match="manifest is invalid"):
        G.require_test_freeze(frozen_root, True)


def test_dry_run_exercises_generator_loader_and_metadata_without_real_inputs(frozen_root, monkeypatch):
    no_real_generation(monkeypatch)
    assert G.main(["--cohort", "test", "--i-confirm-freeze", "--dry-run"], root=frozen_root) == 0
    out = frozen_root / "results/model_runs/dry_run"
    journal = next(out.glob("*.jsonl"))
    parsed = A.load_plans(journal)
    assert [p["case_id"] for p in parsed] == list(G.DRY_RUN_IDS)
    assert json.loads(journal.with_suffix(".json").read_text()) == parsed
    metadata = json.loads(journal.with_suffix(".metadata.json").read_text())
    validate_generation_metadata(metadata, G.load_protocol(frozen_root))
    assert metadata["model"] == "dry-run/fake-client"
    assert metadata["model_digest"].startswith("synthetic-")
    assert metadata["temperature"] == 0.0 and metadata["top_p"] == 1.0
    assert metadata["max_new_tokens"] == 256 and metadata["prompt_sha256"] == A.prompt_sha256()
    descriptor = json.loads(journal.with_suffix(".run.json").read_text())
    assert descriptor["dry_run"] is True and descriptor["num_ctx"] == 8192
    assert "eligibility_manifest_file_sha256" in descriptor
    assert not journal.with_suffix(".lock").exists()


def test_resume_does_not_repeat_recorded_cases_or_allow_changed_settings(frozen_root, monkeypatch):
    no_real_generation(monkeypatch)
    calls = []
    original = G.FakeClient.chat
    def chat(self, *args, **kwargs):
        calls.append(1)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(G.FakeClient, "chat", chat)
    args = ["--dry-run"]
    G.main(args, root=frozen_root)
    G.main(args, root=frozen_root)
    assert len(calls) == len(G.DRY_RUN_IDS)
    with pytest.raises(SystemExit):
        G.main([*args, "--temperature", "0.5"], root=frozen_root)
    assert len(calls) == len(G.DRY_RUN_IDS)


def test_recorded_parse_failure_stays_missing_on_resume(frozen_root, monkeypatch):
    no_real_generation(monkeypatch)
    calls = []
    def malformed(self, *args, **kwargs):
        calls.append(1)
        return {"message": {"content": "{invalid synthetic JSON"}}
    monkeypatch.setattr(G.FakeClient, "chat", malformed)
    G.main(["--dry-run"], root=frozen_root)
    G.main(["--dry-run"], root=frozen_root)
    journal = next((frozen_root / "results/model_runs/dry_run").glob("*.jsonl"))
    assert len(calls) == 3 and len(journal.read_text().splitlines()) == 3
    assert A.load_plans(journal) == []
    assert json.loads(journal.with_suffix(".json").read_text()) == []


@pytest.mark.parametrize("temperature", ["nan", "-1", "3"])
def test_invalid_temperature_is_rejected_before_data_or_server(frozen_root, monkeypatch, temperature):
    no_real_generation(monkeypatch)
    with pytest.raises(SystemExit):
        G.main(["--temperature", temperature], root=frozen_root)
    assert not (frozen_root / "results/model_runs").exists()


def test_test_seed_must_match_protocol(frozen_root, monkeypatch, capsys):
    no_real_generation(monkeypatch)
    with pytest.raises(SystemExit):
        G.main(["--cohort", "test", "--i-confirm-freeze", "--seed", "42"], root=frozen_root)
    assert "test seed" in capsys.readouterr().err


def test_validation_path_uses_selected_inputs_and_loopback_client(frozen_root, monkeypatch):
    """Exercise the non-dry branch entirely with fake inputs and a fake client."""
    ids = [101, 102]
    selected = []
    hosts = []
    def cohort(cohort, root):
        assert cohort == "validation" and root == frozen_root
        return ids
    def inputs(wanted):
        selected.extend(wanted)
        return {cid: "Synthetic fixture only." for cid in wanted}
    class LocalStub(G.FakeClient):
        def __init__(self, model, host):
            self.model = model
            hosts.append(host)
    monkeypatch.setattr(G, "cohort_ids", cohort)
    monkeypatch.setattr(G, "local_inputs", inputs)
    monkeypatch.setattr(A, "Ollama", LocalStub)
    monkeypatch.setenv("OLLAMA_HOST", "https://must-not-send-records.example")
    assert G.main(["--ollama-model", "synthetic-model"], root=frozen_root) == 0
    assert hosts == ["http://127.0.0.1:11434"] and selected == ids
    journal = next((frozen_root / "results/model_runs").glob("*.jsonl"))
    assert [p["case_id"] for p in A.load_plans(journal)] == ids
    assert json.loads(journal.with_suffix(".metadata.json").read_text())["model"] == "synthetic-model"


def test_generation_errors_do_not_echo_record_text(frozen_root, monkeypatch, capsys):
    no_real_generation(monkeypatch)
    def broken(*args, **kwargs):
        raise ValueError("synthetic-private-record-marker")
    monkeypatch.setattr(A, "generate_plans", broken)
    assert G.main(["--dry-run"], root=frozen_root) == 1
    captured = capsys.readouterr()
    assert "synthetic-private-record-marker" not in captured.out + captured.err
    assert "ValueError" in captured.err
    assert not list((frozen_root / "results/model_runs/dry_run").glob("*.lock"))


def test_cli_dry_run_works_from_another_directory_without_dataset_or_ollama(tmp_path):
    import os
    command = [sys.executable, str(ROOT / "scripts/generate_model_a_plans.py"), "--dry-run", "--out", str(tmp_path / "out")]
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True,
                            env={**os.environ, "MIMIC_DIR": str(tmp_path / "absent-data"), "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    journal = next((tmp_path / "out/dry_run").glob("*.jsonl"))
    assert len(A.load_plans(journal)) == 3
