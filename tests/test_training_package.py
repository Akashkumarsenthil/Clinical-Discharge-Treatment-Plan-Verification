"""Synthetic-only training contract tests; GPU and patient files are never needed."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clinverify.models import training_data as T  # noqa: E402


@pytest.mark.parametrize("task", ["diagnosis", "treatment_plan"])
def test_synthetic_bundle_roundtrip_without_reading_real_files(tmp_path, task, monkeypatch):
    monkeypatch.setattr(T, "local_records", lambda *a: pytest.fail("read clinical files"))
    out = tmp_path / task
    m = T.prepare(ROOT, task=task, out=out, synthetic=True)
    loaded, rows = T.load_bundle(out, ROOT)
    assert m == loaded and m["counts"] == {"train": 8, "val": 4}
    assert all(row["case_id"] < 0 and row["case_id"] != -999 for values in rows.values() for row in values)
    if sys.platform != "win32":
        assert out.stat().st_mode & 0o777 == 0o700
        assert (out / "train.jsonl").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("splits", [
    {"train": [1, 1], "val": [2], "test": [3]},
    {"train": [1], "val": [1], "test": [3]},
    {"train": [1], "val": [2], "test": [2]},
    {"train": [True], "val": [2], "test": [3]},
    {"train": [], "val": [2], "test": [3]},
])
def test_split_leakage_rejected(splits):
    with pytest.raises(T.TrainingError):
        T.validate_splits(splits)


def test_frozen_real_split_hash_is_checked_before_data(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "split.json").write_text("{}")
    (tmp_path / "docs/evaluation_protocol.json").write_text(json.dumps({"split_file": "split.json", "split_sha256": "bad"}))
    with pytest.raises(T.TrainingError, match="split hash"):
        T.frozen_splits(tmp_path)


def test_real_mode_needs_team_decision(tmp_path):
    with pytest.raises(T.TrainingError, match="decision"):
        T.prepare(ROOT, task="diagnosis", out=tmp_path / "out", data_dir=tmp_path)
    assert not (tmp_path / "out").exists()


def test_outputs_inside_repo_and_symlinks_rejected(tmp_path):
    for path in (ROOT / "results/training", ROOT / "new-private-output"):
        with pytest.raises(T.TrainingError, match="outside"):
            T.private_location(path, ROOT)
    link = tmp_path / "repo_link"
    link.symlink_to(ROOT, target_is_directory=True)
    with pytest.raises(T.TrainingError, match="outside"):
        T.private_location(link / "results", ROOT)


def test_bundle_cannot_be_overwritten(tmp_path):
    T.prepare(ROOT, task="diagnosis", out=tmp_path / "bundle", synthetic=True)
    with pytest.raises(T.TrainingError, match="exists"):
        T.prepare(ROOT, task="diagnosis", out=tmp_path / "bundle", synthetic=True)


def test_changed_bundle_and_rehashed_heldout_row_rejected(tmp_path):
    out = tmp_path / "bundle"
    T.prepare(ROOT, task="diagnosis", out=out, synthetic=True)
    path = out / "train.jsonl"
    rows = [json.loads(s) for s in path.read_text().splitlines()]
    rows[0]["case_id"] = -999
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    with pytest.raises(T.TrainingError, match="hash mismatch"):
        T.load_bundle(out, ROOT)
    mpath = out / "manifest.json"
    m = json.loads(mpath.read_text())
    m["files"]["train"] = T.digest(path)
    mpath.write_text(json.dumps(m))
    with pytest.raises(T.TrainingError, match="held-out"):
        T.load_bundle(out, ROOT)


def test_fake_decision_and_target_hash_rejected(tmp_path):
    path = tmp_path / "decision.json"
    d = {"schema_version": 1, "task": "treatment_plan", "approved_by": "REPLACE_ME",
         "approved_on": "2026-01-01", "decision_reference": "team-notes", "target_source": "human_reviewed"}
    path.write_text(json.dumps(d))
    with pytest.raises(T.TrainingError):
        T.decision_record(path, "treatment_plan", None)
    d["approved_by"] = "Reviewer"
    path.write_text(json.dumps(d))
    with pytest.raises(T.TrainingError, match="target file"):
        T.decision_record(path, "treatment_plan", None)


@pytest.mark.parametrize("task", ["diagnosis", "treatment_plan"])
def test_real_preparation_path_on_synthetic_files_with_pinned_protocol(tmp_path, task):
    from clinverify.data.synthetic import generate
    import pandas as pd
    root = tmp_path / "fake_repo"
    (root / "docs").mkdir(parents=True)
    generate(tmp_path / "synthetic_source", n_cases=40)
    ext = tmp_path / "synthetic_source/mimic-iv-ext-cdm-1.1"
    label_map = {cid: label for label, values in json.loads((ext / "pathology_ids.json").read_text()).items() for cid in values}
    ids = sorted(label_map)
    splits = {"train": ids[:30], "val": ids[30:36], "test": ids[36:]}
    source = ext / "history_of_present_illness.csv"
    df = pd.read_csv(source)
    df.loc[df.hadm_id.isin(splits["test"]), "hpi"] = "HELDOUT_SENTINEL_MUST_NOT_REACH_TRAINING"
    df.to_csv(source, index=False)
    split_file = root / "splits.json"
    split_file.write_text(json.dumps({"grouped_by": "subject_id", "splits": splits}))
    (root / "docs/evaluation_protocol.json").write_text(json.dumps({"split_file": "splits.json",
         "split_sha256": T.digest(split_file), "test_cases": 4}))
    decision = tmp_path / "decision.json"
    target_file = tmp_path / "targets.jsonl" if task == "treatment_plan" else None
    approved = {"schema_version": 1, "task": task, "approved_by": "Synthetic test approver",
                "approved_on": "2020-01-01", "decision_reference": "TEST-ONLY",
                "target_source": "ext_cdm_reference_diagnosis" if task == "diagnosis" else "human_reviewed"}
    if target_file:
        target_file.write_text("\n".join(json.dumps({"case_id": cid, "plan": {"diagnosis": label_map[cid],
           "treatments": [], "postop_antibiotic_days": None}}) for cid in splits["train"] + splits["val"]) + "\n")
        approved["targets_sha256"] = T.digest(target_file)
    decision.write_text(json.dumps(approved))
    out = tmp_path / "private_bundle"
    T.prepare(root, task=task, out=out, data_dir=ext, decision=decision, targets=target_file)
    with pytest.raises(T.TrainingError, match="confirm-team"):
        T.load_bundle(out, root)
    m, loaded = T.load_bundle(out, root, allow_real=True)
    assert not m["synthetic"] and len(loaded["train"]) == 30 and len(loaded["val"]) == 6
    assert "HELDOUT_SENTINEL" not in (out / "train.jsonl").read_text() + (out / "val.jsonl").read_text()


@pytest.mark.parametrize("change", [
    {"facts": {}}, {"verdict": "valid"}, {"postop_antibiotic_days": True},
    {"treatments": ["invented"]}, {"treatments": ["antibiotics", "antibiotics"]},
])
def test_invalid_plan_targets_rejected(change):
    plan = {"diagnosis": "appendicitis", "treatments": [], "postop_antibiotic_days": None, **change}
    with pytest.raises(T.TrainingError):
        T.plan_target(plan)


def test_plan_targets_refuse_test_and_missing_cases(tmp_path):
    path = tmp_path / "plans.jsonl"
    splits = {"train": [1], "val": [2], "test": [3]}
    plan = {"diagnosis": "appendicitis", "treatments": [], "postop_antibiotic_days": None}
    path.write_text(json.dumps({"case_id": 3, "plan": plan}) + "\n")
    with pytest.raises(T.TrainingError, match="held-out"):
        T.read_targets(path, splits)
    path.write_text(json.dumps({"case_id": 1, "plan": plan}) + "\n")
    with pytest.raises(T.TrainingError, match="every train"):
        T.read_targets(path, splits)


def test_reader_matches_existing_model_a_formatter_and_ignores_forbidden_tables(tmp_path):
    from clinverify.data import ext_cdm as E
    from clinverify.data.synthetic import generate
    from clinverify.models import model_a as A
    import pandas as pd
    generate(tmp_path / "data", n_cases=40)
    ext = tmp_path / "data/mimic-iv-ext-cdm-1.1"
    tables, _ = E.clean_tables(E.load_tables(ext))
    expected = A.case_inputs(E.transform_tables(tables, ext))
    ids = set(sorted(expected)[:3])
    # Fail if a retrospective CSV is ever opened by the new reader.
    for name in ["discharge_diagnosis", "icd_diagnosis", "icd_procedures", "discharge_procedures"]:
        (ext / (name + ".csv")).write_text("FORBIDDEN FILE MUST NOT BE OPENED")
    inputs, labels, hashes = T.local_records(ext, ids)
    assert inputs == {cid: expected[cid] for cid in sorted(ids)}
    assert set(labels) == ids and len(hashes) == 7
    assert set(hashes) == {n + ".csv" for n in T.TABLES} | {"lab_test_mapping.csv", "pathology_ids.json"}


class TinyTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return [1, 2, 3] if add_generation_prompt else [1, 2, 3, 4, 5]


def test_completion_mask_and_overlength_fail_closed():
    row = {"system": "s", "user": "u", "completion": "c"}
    result = T.encode_row(TinyTokenizer(), row, 5)
    assert result["labels"] == [-100, -100, -100, 4, 5]
    with pytest.raises(T.TrainingError, match="nothing is truncated"):
        T.encode_row(TinyTokenizer(), row, 4)


def test_ambiguous_template_rejected():
    class Wrong(TinyTokenizer):
        def apply_chat_template(self, messages, tokenize, add_generation_prompt):
            return [8, 9] if add_generation_prompt else [1, 2, 3]
    with pytest.raises(T.TrainingError, match="boundary"):
        T.encode_row(Wrong(), {"system": "s", "user": "u", "completion": "c"}, 20)


def test_cli_sanitizes_unexpected_error(tmp_path):
    decision = tmp_path / "decision.json"
    decision.write_text("SYNTHETIC_SECRET_SENTINEL not json")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/prepare_model_a_training.py"),
                        "--task", "diagnosis", "--data-dir", str(tmp_path), "--decision", str(decision),
                        "--out", str(tmp_path / "out")], text=True, capture_output=True)
    assert r.returncode == 2
    assert "SYNTHETIC_SECRET_SENTINEL" not in r.stdout + r.stderr


@pytest.mark.parametrize("task", ["diagnosis", "treatment_plan"])
def test_cpu_smoke_really_updates_and_saves_adapter(tmp_path, task):
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    pytest.importorskip("peft")
    import argparse
    from clinverify.models.finetune import run
    bundle, out = tmp_path / "bundle", tmp_path / "run"
    T.prepare(ROOT, task=task, out=bundle, synthetic=True)
    a = argparse.Namespace(bundle=bundle, out=out, model_dir=None, cpu_smoke=True, preflight=False,
         load_in_4bit=False, i_confirm_team_decision=False, seed=298, epochs=1.0, max_steps=2,
         learning_rate=2e-4, max_length=1024, batch_size=1, gradient_accumulation=1,
         lora_rank=2, lora_alpha=4, validation_generations=2, max_new_tokens=16)
    result = run(a, ROOT)
    assert result["global_step"] == 2 and result["synthetic"]
    assert (out / "adapter/adapter_model.safetensors").is_file()
    assert (out / "smoke_base/config.json").is_file()
    assert json.loads((out / "validation_scores.json").read_text())["requested"] == 2
    history = json.loads((out / "loss_history.json").read_text())
    assert any("loss" in x for x in history) and any("eval_loss" in x for x in history)
    from safetensors.torch import load_file
    tensors = load_file(out / "adapter/adapter_model.safetensors")
    # LoRA B starts at zero. A nonzero B proves an optimizer update occurred.
    assert any(t.abs().sum().item() > 0 for k, t in tensors.items() if "lora_B" in k)
    from transformers import AutoModelForCausalLM
    from peft import PeftModel
    restored = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(out / "smoke_base", local_files_only=True),
                                        out / "adapter", local_files_only=True)
    assert restored.peft_config["default"].r == 2
    with pytest.raises(T.TrainingError, match="exists"):
        run(a, ROOT)
