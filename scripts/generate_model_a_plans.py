"""Generate Model A plans locally, with an explicit freeze guard for test runs.

Safe, data-free check (no Ollama, GPU, patient records or frozen case IDs):
    python scripts/generate_model_a_plans.py --cohort validation --dry-run

Real validation (local Ext-CDM in MIMIC_DIR, local Ollama required):
    python scripts/generate_model_a_plans.py --cohort validation --seed 298

Only after human freeze/sign-off, on the GPU machine:
    python scripts/generate_model_a_plans.py --cohort test --seed 298 --i-confirm-freeze

Repeat with protocol seeds 299 and 300, keeping the other settings fixed. Never
rerun to select a better answer. The existing generator resumes recorded cases,
including recorded parse failures, without generating them again. Changing a
run's settings in the same output directory is refused.

Writes the notebook-compatible .jsonl and .metadata.json files, plus a .json
list accepted by verify_model_plans.py. Pass the .json list (not .jsonl) to that
CLI and its .metadata.json to --generation-metadata. The .run.json sidecar records
cohort, context limit and freeze hashes; it is not the generation-metadata file.
Keep all run artifacts local. A dry run uses a fake model and separate dry_run/
directory, and must never be reported as model performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.eval.adjudication import validate_eligibility_manifest  # noqa: E402
from clinverify.eval.protocol import cohort_ids, load_protocol, validate_generation_metadata  # noqa: E402
from clinverify.models import model_a as A  # noqa: E402

TOP_P = 1.0
MAX_NEW_TOKENS = 256
NUM_CTX = 8192
DRY_RUN_IDS = (-1, -2, -3)


class ConfigurationError(ValueError):
    """A safe, record-free error that can be shown on the console."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_test_freeze(root: Path, confirmed: bool) -> dict:
    """Check the guard before reading case inputs, contacting Ollama or writing output.

    This checks files/declarations, not whether human review actually happened.
    The same guard applies to --dry-run --cohort test.
    """
    manifest = root / "results/eligibility_manifest.json"
    checklist = root / "docs/model_a_freeze_checklist.md"
    failed = []
    if not confirmed:
        failed.append("test guard: --i-confirm-freeze is required")
    if not manifest.is_file():
        failed.append("test guard: results/eligibility_manifest.json is missing")
    if not checklist.is_file():
        failed.append("test guard: docs/model_a_freeze_checklist.md is missing")
    else:
        text = checklist.read_text()
        unchecked = len(re.findall(r"\[\s*\]", text))
        if unchecked:
            failed.append(f"test guard: freeze checklist has {unchecked} unticked [ ] boxes")
        elif not re.search(r"\[[xX]\]", text):
            failed.append("test guard: freeze checklist has no checked boxes")
    if failed:
        raise ConfigurationError("\n".join(failed))

    # A placeholder/empty file must not unlock test generation. Validate IDs and
    # decisions against the protocol's frozen membership hash, without loading facts.
    try:
        protocol = load_protocol(root)
        data = json.loads(manifest.read_text())
        ids = [row["case_id"] for row in data["cases"]]
        if any(type(cid) is not int for cid in ids):
            raise ConfigurationError("non-integer case ID")
        digest = hashlib.sha256(json.dumps(sorted(ids), separators=(",", ":")).encode()).hexdigest()
        if len(ids) != protocol["supported_test_cases"] or digest != protocol["supported_test_ids_sha256"]:
            raise ConfigurationError("covered cohort mismatch")
        validate_eligibility_manifest(data, covered_case_ids=set(ids), catalog_version=protocol["catalog_version"])
    except (ValueError, KeyError, TypeError) as err:
        raise ConfigurationError("test guard: eligibility manifest is invalid or does not match the frozen covered cohort") from err
    return {"eligibility_manifest_file_sha256": sha256(manifest), "freeze_checklist_sha256": sha256(checklist)}


class FakeClient:
    """Fixed synthetic responses; never contacts a server or reads case records."""
    model = "dry-run/fake-client"

    def digest(self):
        return "synthetic-fixed-plan-v1"

    def chat(self, system, user, **settings):
        return {"message": {"content": json.dumps({
            "diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"],
            "postop_antibiotic_days": 0,
        })}}


def local_inputs(ids):
    """Reuse the notebook preprocessing path; only A.case_inputs feeds the LLM.

    Retrospective columns may be loaded by the shared transformer for its master
    table, but case_inputs excludes them. Never print the transformed records.
    """
    from clinverify.data import ext_cdm as E

    cleaned, _ = E.clean_tables(E.load_tables())
    cleaned.pop("lab_test_mapping", None)
    inputs = A.case_inputs(E.transform_tables(cleaned), ids)
    if set(inputs) != set(ids):
        raise ConfigurationError("selected cohort does not have complete model inputs")
    return inputs


def write_json(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=1) + "\n")
    temp.replace(path)


def run(args, root: Path):
    freeze = require_test_freeze(root, args.i_confirm_freeze) if args.cohort == "test" else {}
    if not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2:
        raise ConfigurationError("temperature must be finite and between 0 and 2")
    protocol = load_protocol(root)
    if args.cohort == "test" and args.seed not in protocol["generation_seeds"]:
        raise ConfigurationError(f"test seed must be one of {protocol['generation_seeds']}")

    if args.dry_run:
        ids = list(DRY_RUN_IDS)
        inputs = {cid: "Synthetic fixture only; no patient data." for cid in ids}
        client = FakeClient()
    else:
        ids = cohort_ids(args.cohort, root)
        # Use only the machine's local server, even if OLLAMA_HOST names a hosted service.
        client = A.Ollama(args.ollama_model, host="http://127.0.0.1:11434")
        inputs = None
    metadata = {"model": client.model, "model_digest": client.digest(), "prompt_sha256": A.prompt_sha256(),
                "seed": args.seed, "temperature": args.temperature, "top_p": TOP_P, "max_new_tokens": MAX_NEW_TOKENS}
    if args.cohort == "test":
        try:
            validate_generation_metadata(metadata, protocol)
        except ValueError as err:
            raise ConfigurationError(str(err)) from err

    out = args.out if args.out is not None else root / "results/model_runs"
    if args.dry_run:
        out = out / "dry_run"
    model_tag = re.sub(r"[^A-Za-z0-9_.-]", "_", metadata["model"])
    tag = "val" if args.cohort == "validation" else "test"
    stem = f"model_a_{model_tag}_{tag}_seed{args.seed}"
    plans_path = out / (stem + ".jsonl")
    metadata_path = plans_path.with_suffix(".metadata.json")
    run_path = plans_path.with_suffix(".run.json")
    list_path = plans_path.with_suffix(".json")
    descriptor = {"cohort": args.cohort, "dry_run": args.dry_run, "num_ctx": NUM_CTX,
                  "protocol_sha256": sha256(root / "docs/evaluation_protocol.json"),
                  "generator_sha256": sha256(Path(__file__)), "model_a_sha256": sha256(Path(A.__file__)),
                  "case_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(), **freeze}
    out.mkdir(parents=True, exist_ok=True)
    # Avoid simultaneous processes making two attempts for the same case.
    lock = plans_path.with_suffix(".lock")
    try:
        lock_handle = lock.open("x")
    except FileExistsError as err:
        raise ConfigurationError("run is locked; check for an active or interrupted process before resuming") from err
    try:
        with lock_handle:
            # Existing JSONL must carry matching settings before the generator can resume.
            for path, expected in ((metadata_path, metadata), (run_path, descriptor)):
                if path.exists():
                    if json.loads(path.read_text()) != expected:
                        raise ConfigurationError("existing run settings differ; refusing to mix generations")
                elif plans_path.exists():
                    raise ConfigurationError("existing JSONL lacks run metadata; refusing an unverified resume")
            if plans_path.exists():
                saved = [json.loads(line) for line in plans_path.read_text().splitlines() if line.strip()]
                seen = [row["case_id"] for row in saved]
                if len(seen) != len(set(seen)) or not set(seen) <= set(ids):
                    raise ConfigurationError("existing JSONL has duplicate or out-of-cohort case IDs")
            if inputs is None:
                inputs = local_inputs(ids)
            write_json(metadata_path, metadata)
            write_json(run_path, descriptor)
            try:
                A.generate_plans(client, inputs, ids, plans_path, seed=args.seed, temperature=args.temperature,
                                 top_p=TOP_P, max_new_tokens=MAX_NEW_TOKENS, num_ctx=NUM_CTX)
            finally:
                # A partial run still has a loader-compatible list; omitted plans
                # remain missing outputs under the fixed-cohort scorer.
                if plans_path.exists():
                    write_json(list_path, A.load_plans(plans_path))
    finally:
        lock.unlink()
    print("DRY RUN — synthetic plumbing check only" if args.dry_run else "Local generation complete")
    print(f"Scheduled: {len(ids)}; parsed plans: {len(A.load_plans(plans_path))}")
    print("Resumable JSONL:", plans_path)
    print("Verifier JSON list:", list_path)
    print("Generation metadata:", metadata_path)
    return 0


def main(argv=None, *, root: Path = ROOT):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cohort", choices=("validation", "test"), default="validation")
    parser.add_argument("--seed", type=int, default=298)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--out", type=Path, help="output directory (default results/model_runs/)")
    parser.add_argument("--ollama-model", default="qwen2.5:14b")
    parser.add_argument("--i-confirm-freeze", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="fake client and invented IDs; never loads real cohort data")
    args = parser.parse_args(argv)
    try:
        return run(args, root)
    except ConfigurationError as err:
        # Configuration errors above contain no record text. Other failures are
        # caught below without their potentially data-bearing exception messages.
        parser.error(str(err))
    except Exception as err:
        print(f"Generation stopped: {type(err).__name__}. Inspect the local environment; no record text printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
