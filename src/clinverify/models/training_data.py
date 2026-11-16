"""Private development-only SFT bundles. No held-out records or clinical labels invented."""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import date
from pathlib import Path

from clinverify.models import model_a as A
from clinverify.plan import DIAGNOSES, TREATMENT_CONCEPTS

TABLES = ("history_of_present_illness", "physical_examination", "laboratory_tests",
          "microbiology", "radiology_reports")
DIAGNOSIS_SYSTEM = ('Given the admission record, return JSON only with one field, "diagnosis", '
                    'chosen from appendicitis, cholecystitis, diverticulitis, pancreatitis.')


class TrainingError(ValueError):
    """Fixed messages only: safe to show without patient records or targets."""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def private_location(path: Path, root: Path) -> Path:
    path, root = Path(path).expanduser().resolve(), Path(root).resolve()
    if path == root or root in path.parents or any((p / ".git").exists() for p in [path, *path.parents]):
        raise TrainingError("output must be outside every Git checkout, including symlink targets")
    return path


def new_private_dir(path: Path, root: Path) -> Path:
    path = private_location(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        raise TrainingError("output already exists; choose a fresh directory") from None
    return path


def write_json(path: Path, obj) -> None:
    with Path(path).open("x", encoding="utf-8") as f:
        os.chmod(path, 0o600)
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write("\n")


def validate_splits(splits: dict) -> None:
    if not isinstance(splits, dict) or set(splits) != {"train", "val", "test"}:
        raise TrainingError("split document must contain train, val and test")
    seen = set()
    for values in splits.values():
        if not isinstance(values, list) or not values or any(type(h) is not int for h in values):
            raise TrainingError("each split needs nonempty integer case IDs")
        if len(set(values)) != len(values) or seen.intersection(values):
            raise TrainingError("duplicate or overlapping split IDs")
        seen.update(values)


def frozen_splits(root: Path) -> tuple[dict, str]:
    protocol = json.loads((root / "docs/evaluation_protocol.json").read_text())
    path = root / protocol["split_file"]
    if digest(path) != protocol["split_sha256"]:
        raise TrainingError("split hash differs from the committed evaluation protocol")
    doc = json.loads(path.read_text())
    splits = doc["splits"]
    validate_splits(splits)
    if doc.get("grouped_by") != "subject_id" or len(splits["test"]) != protocol["test_cases"]:
        raise TrainingError("expected frozen patient-grouped splits")
    return splits, digest(path)


def decision_record(path: Path, task: str, targets: Path | None) -> dict:
    d = json.loads(path.read_text())
    keys = {"schema_version", "task", "approved_by", "approved_on", "decision_reference", "target_source"}
    if not keys <= d.keys() or d["schema_version"] != 1 or d["task"] != task:
        raise TrainingError("missing or mismatched team decision record")
    for k in keys - {"schema_version", "task", "approved_on"}:
        if not isinstance(d[k], str) or not d[k].strip() or d[k].startswith("REPLACE"):
            raise TrainingError("team decision needs named approver, reference and target source")
    try:
        approved_on = date.fromisoformat(d["approved_on"])
    except (ValueError, TypeError):
        raise TrainingError("decision date must be YYYY-MM-DD") from None
    if approved_on > date.today():
        raise TrainingError("decision date cannot be in the future")
    if task == "diagnosis" and d["target_source"] != "ext_cdm_reference_diagnosis":
        raise TrainingError("diagnosis training uses the Ext-CDM reference diagnosis")
    if task == "treatment_plan":
        if targets is None or d.get("targets_sha256") != digest(targets):
            raise TrainingError("plan training needs a target file pinned by the team decision hash")
        if d["target_source"] not in {"human_authored", "human_reviewed", "approved_external_targets"}:
            raise TrainingError("plan target source must be explicitly approved; verdicts are not targets")
    return {k: d[k] for k in keys} | ({"targets_sha256": d["targets_sha256"]} if targets else {})


def plan_target(obj: dict) -> dict:
    if not isinstance(obj, dict) or set(obj) != {"diagnosis", "treatments", "postop_antibiotic_days"}:
        raise TrainingError("plan target has missing or extra fields; facts and verdicts are forbidden")
    if obj["diagnosis"] not in DIAGNOSES:
        raise TrainingError("unsupported target diagnosis")
    ts, days = obj["treatments"], obj["postop_antibiotic_days"]
    if (not isinstance(ts, list) or any(not isinstance(t, str) or t not in TREATMENT_CONCEPTS for t in ts)
            or len(ts) != len(set(ts))):
        raise TrainingError("invalid or duplicate target treatment concepts")
    if days is not None and (type(days) is not int or days < 0):
        raise TrainingError("target antibiotic days must be a nonnegative integer or null")
    return obj


def read_targets(path: Path, splits: dict) -> dict[int, dict]:
    allowed = set(splits["train"]) | set(splits["val"])
    targets = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict) or set(obj) != {"case_id", "plan"}:
            raise TrainingError("target rows must contain only case_id and plan")
        cid = obj["case_id"]
        if type(cid) is not int or cid not in allowed or cid in targets:
            raise TrainingError("target contains a duplicate, held-out or unknown case ID")
        targets[cid] = plan_target(obj["plan"])
    if set(targets) != allowed:
        raise TrainingError("targets must cover every train and validation case; no silent filtering")
    return targets


def local_records(directory: Path, ids: set[int]) -> tuple[dict[int, str], dict[int, str], dict]:
    """Read only allowed CSVs, filter IDs before preprocessing; never read retrospective tables.

    lab flagging/text normalization match ext_cdm.transform_tables, then reuse
    model_a.case_inputs, including its fixed row/text limits. No admissions file needed.
    """
    import pandas as pd

    tables, hashes = {}, {}
    for name in TABLES:
        path = directory / (name + ".csv")
        hashes[path.name] = digest(path)
        parts = [chunk[chunk.hadm_id.isin(ids)] for chunk in pd.read_csv(path, chunksize=20000)]
        tables[name] = pd.concat(parts, ignore_index=True).drop_duplicates()
    for name, col in [("history_of_present_illness", "hpi"), ("physical_examination", "pe"),
                      ("radiology_reports", "text")]:
        tables[name][col] = tables[name][col].fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    for name in TABLES[:2]:
        if tables[name].hadm_id.duplicated().any() or set(tables[name].hadm_id) != ids:
            raise TrainingError("history/examination coverage or uniqueness check failed")
    labs = tables["laboratory_tests"]
    num = labs.valuestr.astype(str).str.extract(r"^\s*[<>]=?\s*(-?\d+(?:\.\d+)?)|^\s*(-?\d+(?:\.\d+)?)")
    value = pd.to_numeric(num[0].fillna(num[1]), errors="coerce")
    valid = value.notna() & labs.ref_range_lower.notna() & labs.ref_range_upper.notna()
    labs["flag"] = "unknown"
    labs.loc[valid & (value < labs.ref_range_lower), "flag"] = "low"
    labs.loc[valid & (value > labs.ref_range_upper), "flag"] = "high"
    labs.loc[valid & value.between(labs.ref_range_lower, labs.ref_range_upper), "flag"] = "normal"
    mapping_path = directory / "lab_test_mapping.csv"
    mapping = pd.read_csv(mapping_path).dropna(subset=["itemid"]).drop_duplicates("itemid")
    tables["laboratory_tests"] = labs.merge(mapping[["itemid", "label"]], on="itemid", how="left")
    hashes[mapping_path.name] = digest(mapping_path)
    ids_path = directory / "pathology_ids.json"
    hashes[ids_path.name] = digest(ids_path)
    labels = {}
    for pathology, values in json.loads(ids_path.read_text()).items():
        for cid in values:
            if cid in ids:
                if cid in labels or pathology not in DIAGNOSES:
                    raise TrainingError("invalid reference diagnosis mapping")
                labels[cid] = pathology
    if set(labels) != ids:
        raise TrainingError("reference diagnoses do not cover development cases")
    return A.case_inputs(tables, sorted(ids)), labels, hashes


def rows_for(task: str, splits: dict, inputs: dict, labels: dict, targets: dict | None) -> dict:
    rows = {}
    system = A.SYSTEM_PROMPT if task == "treatment_plan" else DIAGNOSIS_SYSTEM
    for split in ("train", "val"):
        rows[split] = []
        for cid in splits[split]:
            completion = targets[cid] if targets is not None else {"diagnosis": labels[cid]}
            if completion["diagnosis"] != labels[cid]:
                raise TrainingError("target diagnosis disagrees with benchmark reference")
            rows[split].append({"case_id": cid, "system": system,
                                "user": A.USER_TEMPLATE.format(case_id=cid, record=inputs[cid]),
                                "completion": json.dumps(completion, sort_keys=True)})
    return rows


def synthetic_rows(task: str) -> tuple[dict, dict]:
    splits = {"train": list(range(-1, -9, -1)), "val": [-101, -102, -103, -104], "test": [-999]}
    ids = splits["train"] + splits["val"]
    labels = {cid: DIAGNOSES[i % len(DIAGNOSES)] for i, cid in enumerate(ids)}
    inputs = {cid: "SYNTHETIC software fixture. Not a patient or clinical training example." for cid in ids}
    targets = {cid: {"diagnosis": labels[cid], "treatments": [], "postop_antibiotic_days": None} for cid in ids}
    return splits, rows_for(task, splits, inputs, labels, targets if task == "treatment_plan" else None)


def prepare(root: Path, *, task: str, out: Path, synthetic: bool = False,
            data_dir: Path | None = None, decision: Path | None = None, targets: Path | None = None) -> dict:
    if task not in {"diagnosis", "treatment_plan"}:
        raise TrainingError("task must be diagnosis or treatment_plan")
    private_location(out, root)
    if synthetic:
        if any(v is not None for v in (data_dir, decision, targets)):
            raise TrainingError("synthetic mode cannot read real data, decisions or targets")
        splits, rows = synthetic_rows(task)
        sources, approved, split_hash = {}, None, None
    else:
        if decision is None or data_dir is None:
            raise TrainingError("real preparation needs --data-dir and a completed --decision record")
        if task == "diagnosis" and targets is not None:
            raise TrainingError("diagnosis mode does not accept plan targets")
        splits, split_hash = frozen_splits(root)
        approved = decision_record(decision, task, targets)
        target_rows = read_targets(targets, splits) if task == "treatment_plan" else None
        ids = set(splits["train"]) | set(splits["val"])
        inputs, labels, sources = local_records(data_dir, ids)
        rows = rows_for(task, splits, inputs, labels, target_rows)
    out = new_private_dir(out, root)
    for name, values in rows.items():
        p = out / (name + ".jsonl")
        with p.open("x") as f:
            os.chmod(p, 0o600)
            for value in values:
                f.write(json.dumps(value) + "\n")
    manifest = {"schema_version": 1, "task": task, "synthetic": synthetic,
                "split_sha256": split_hash, "source_sha256": sources, "decision": approved,
                "input_prompt_sha256": A.prompt_sha256(), "diagnosis_system_sha256": json_digest(DIAGNOSIS_SYSTEM),
                "counts": {k: len(v) for k, v in rows.items()},
                "files": {k: digest(out / (k + ".jsonl")) for k in rows}}
    write_json(out / "manifest.json", manifest)
    return manifest


def load_bundle(bundle: Path, root: Path, allow_real: bool = False) -> tuple[dict, dict]:
    private_location(bundle, root)
    m = json.loads((bundle / "manifest.json").read_text())
    if (m.get("schema_version") != 1 or type(m.get("synthetic")) is not bool
            or m.get("task") not in {"diagnosis", "treatment_plan"}):
        raise TrainingError("unsupported training bundle")
    if m["synthetic"]:
        splits, _ = synthetic_rows(m["task"])
    else:
        if not allow_real:
            raise TrainingError("real training requires --i-confirm-team-decision")
        splits, split_hash = frozen_splits(root)
        if m.get("split_sha256") != split_hash or not m.get("decision"):
            raise TrainingError("bundle lacks pinned development splits or team decision")
    if (m.get("input_prompt_sha256") != A.prompt_sha256()
            or m.get("diagnosis_system_sha256") != json_digest(DIAGNOSIS_SYSTEM)):
        raise TrainingError("input formatter or prompt changed; prepare a new bundle")
    rows = {}
    for name in ("train", "val"):
        path = bundle / (name + ".jsonl")
        if digest(path) != m["files"][name]:
            raise TrainingError("prepared dataset hash mismatch")
        rows[name] = [json.loads(line) for line in path.read_text().splitlines()]
        got = [r["case_id"] for r in rows[name]]
        if got != splits[name] or len(got) != m["counts"][name]:
            raise TrainingError("prepared dataset contains missing, reordered or held-out cases")
        expected_system = A.SYSTEM_PROMPT if m["task"] == "treatment_plan" else DIAGNOSIS_SYSTEM
        for row in rows[name]:
            if (set(row) != {"case_id", "system", "user", "completion"}
                    or row["system"] != expected_system or not isinstance(row["user"], str) or not row["user"].strip()):
                raise TrainingError("invalid prepared row")
            target = json.loads(row["completion"])
            if m["task"] == "treatment_plan":
                plan_target(target)
            elif not isinstance(target, dict) or set(target) != {"diagnosis"} or target["diagnosis"] not in DIAGNOSES:
                raise TrainingError("invalid diagnosis target")
    return m, rows


def encode_row(tokenizer, row: dict, max_length: int) -> dict:
    messages = [{"role": "system", "content": row["system"]}, {"role": "user", "content": row["user"]}]
    prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    tokens = tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": row["completion"]}],
                                           tokenize=True, add_generation_prompt=False)
    if tokens[:len(prefix)] != prefix or len(tokens) <= len(prefix):
        raise TrainingError("chat template has no unambiguous completion boundary")
    if len(tokens) > max_length:
        raise TrainingError("record exceeds max length; increase it or agree a versioned input policy; nothing is truncated")
    return {"input_ids": tokens, "attention_mask": [1] * len(tokens),
            "labels": [-100] * len(prefix) + tokens[len(prefix):]}


def training_settings(args) -> None:
    for key in ("max_length", "batch_size", "gradient_accumulation", "lora_rank", "lora_alpha", "validation_generations", "max_new_tokens"):
        value = getattr(args, key)
        if type(value) is not int or value < (0 if key == "validation_generations" else 1):
            raise TrainingError("invalid positive integer training setting")
    if args.max_steps != -1 and args.max_steps < 1:
        raise TrainingError("max steps must be -1 or a positive integer")
    if args.seed < 0:
        raise TrainingError("seed must be nonnegative")
    for value in (args.epochs, args.learning_rate):
        if not math.isfinite(value) or value <= 0:
            raise TrainingError("epochs and learning rate must be finite and positive")
