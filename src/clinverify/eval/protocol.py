"""Versioned evaluation contract and non-patient run provenance."""
from __future__ import annotations

import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def load_protocol(root: Path = ROOT) -> dict:
    return json.loads((root / "docs/evaluation_protocol.json").read_text())


def cohort_ids(cohort: str, root: Path = ROOT):
    if cohort == "pilot":
        return None
    if cohort not in ("validation", "test"):
        raise ValueError("cohort must be pilot, validation or test")
    protocol = load_protocol(root)
    split = root / protocol["split_file"]
    if hashlib.sha256(split.read_bytes()).hexdigest() != protocol["split_sha256"]:
        raise ValueError("split file differs from the frozen protocol")
    data = json.loads(split.read_text())
    ids = data["splits"]["val" if cohort == "validation" else "test"]
    if cohort == "test" and len(ids) != protocol["test_cases"]:
        raise ValueError("held-out test cohort must contain exactly 100 cases")
    return ids


def validate_generation_metadata(metadata: dict, protocol: dict) -> None:
    required = ("model", "model_digest", "prompt_sha256", "seed", "temperature", "top_p", "max_new_tokens")
    if not isinstance(metadata, dict) or any(k not in metadata for k in required):
        raise ValueError("test runs require model, model_digest, prompt_sha256, seed, temperature, top_p, max_new_tokens")
    if set(metadata) - set(required):
        raise ValueError("unexpected generation metadata fields; do not include patient text")
    if not all(isinstance(metadata[k], str) and metadata[k].strip() for k in ("model", "model_digest")):
        raise ValueError("model and model_digest must identify the exact local model")
    prompt_hash = metadata["prompt_sha256"]
    if not isinstance(prompt_hash, str) or len(prompt_hash) != 64 or any(c not in "0123456789abcdef" for c in prompt_hash):
        raise ValueError("prompt_sha256 must be a lowercase SHA-256 hash")
    if type(metadata["seed"]) is not int or metadata["seed"] not in protocol["generation_seeds"]:
        raise ValueError("test generation seed is not in the frozen protocol")
    for key, maximum in (("temperature", 2), ("top_p", 1)):
        value = metadata[key]
        if type(value) not in (int, float) or not 0 <= value <= maximum or (key == "top_p" and value == 0):
            raise ValueError(f"invalid generation setting: {key}")
    if type(metadata["max_new_tokens"]) is not int or metadata["max_new_tokens"] <= 0:
        raise ValueError("max_new_tokens must be a positive integer")


def treatment_cohort_record(expected_ids, case_facts, protocol, *, formal_test=False):
    if not set(expected_ids) <= set(case_facts):
        raise ValueError("record facts are missing for a selected cohort case")
    supported = sorted(h for h in expected_ids
                       if case_facts[h]["pathology"] in protocol["treatment_diagnoses"])
    digest = hashlib.sha256(json.dumps(supported, separators=(",", ":")).encode()).hexdigest()
    if formal_test and (len(supported) != protocol["supported_test_cases"]
                        or digest != protocol["supported_test_ids_sha256"]):
        raise ValueError("covered treatment cohort differs from the frozen 73-case selection")
    return {"scheduled_diagnosis_cases": len(expected_ids), "scheduled_treatment_cases": len(supported),
            "unsupported_treatment_cases": len(expected_ids) - len(supported), "supported_case_ids_sha256": digest}


def run_provenance(root: Path = ROOT) -> dict:
    protocol = load_protocol(root)
    paths = ["docs/evaluation_protocol.json", "src/clinverify/rules/catalog.py",
             "src/clinverify/data/case_facts.py", "src/clinverify/data/case_loader.py",
             "src/clinverify/eval/model_run.py", "src/clinverify/eval/harness.py", "src/clinverify/eval/protocol.py",
             "src/clinverify/eval/adjudication.py",
             "src/clinverify/verifier/z3_verifier.py", "docs/rule_signoff.md", protocol["split_file"]]
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                    capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", None
    return {"protocol_version": protocol["version"], "fact_mode": protocol["fact_mode"],
            "catalog_version": protocol["catalog_version"], "git_commit": commit, "working_tree_dirty": dirty,
            "source_sha256": hashes, "rule_second_review": "not certified by runner; see hashed sign-off record",
            "python_version": sys.version.split()[0], "z3_solver_version": version("z3-solver"),
            "manual_fact_audit": "not certified by runner; human answers are never auto-filled"}
