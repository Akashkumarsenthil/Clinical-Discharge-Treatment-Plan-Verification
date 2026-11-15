"""Evaluation summary for one Model A run: diagnosis metrics plus the verifier's plan metrics (aggregates only).

Run from the repository root after verify_model_plans.py has written its run_*.json into --verify-dir:
    python scripts/summarize_model_run.py --plans RUN/model_a_qwen2.5_14b_val_seed298.json \
        --verify-dir RUN --cohort validation --out RUN

Diagnosis: accuracy, macro F1 over the four pathologies and per-pathology recall, against the reference pathology
from the record. In a fixed cohort (validation/test) a case with no parsed plan counts as a wrong diagnosis.
Plans: checked acceptance, joint success, verdict counts and violations by rule, copied from the verifier run.
Writes evaluation_summary.json with counts, rates, rule IDs and run settings; no record or plan text.
For a data-free check pass --facts-json (a {"<case_id>": {"pathology": ...}} file) and --split-file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.plan import DIAGNOSES  # noqa: E402

MISSING = "missing"
VERIFY_KEYS = (
    "scoring_population", "n_plans", "n_submitted", "n_missing_outputs", "n_unparseable", "diagnosis_accuracy",
    "n_supported_cases", "supported_checked_acceptance_rate", "n_supported_checked_accepted",
    "supported_treatment_validity_rate", "joint_success_rate", "validity_rate", "status", "checked_treatment_status",
    "violations_by_rule", "solver_ms_mean", "solver_ms_p95",
)


def macro_f1(y_true: list[str], y_pred: list[str], labels=DIAGNOSES) -> float:
    """Unweighted mean F1 over the given labels (same as sklearn's average="macro" with labels= and zero_division=0).
    A prediction outside the labels, such as "missing", is only a false negative for the true class."""
    scores = []
    for c in labels:
        tp = sum(t == c and p == c for t, p in zip(y_true, y_pred))
        fp = sum(t != c and p == c for t, p in zip(y_true, y_pred))
        fn = sum(t == c and p != c for t, p in zip(y_true, y_pred))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores)


def diagnosis_metrics(predicted: dict[int, str], reference: dict[int, str]) -> dict:
    """Accuracy, macro F1 and per-pathology recall over the reference cases; absent predictions count as wrong."""
    ids = sorted(reference)
    if not ids:
        return {"n": 0, "accuracy": None, "macro_f1": None, "n_missing": 0, "per_pathology": {}}
    y_true = [reference[h] for h in ids]
    y_pred = [predicted.get(h) or MISSING for h in ids]
    per = {}
    for d in DIAGNOSES:
        rows = [k for k, t in enumerate(y_true) if t == d]
        per[d] = {"n": len(rows), "recall": (sum(y_pred[k] == d for k in rows) / len(rows)) if rows else None}
    return {
        "n": len(ids),
        "accuracy": sum(t == p for t, p in zip(y_true, y_pred)) / len(ids),
        "macro_f1": macro_f1(y_true, y_pred),
        "n_missing": sum(p == MISSING for p in y_pred),
        "per_pathology": per,
    }


def latest_verify_run(directory: Path) -> tuple[Path, dict]:
    """Newest verify_model_plans.py summary in the directory (run_eval.py logs there do not qualify)."""
    found = []
    for path in directory.glob("run_*.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and "scoring_population" in data and "per_case" in data:
            found.append((path.stat().st_mtime, path.name, path, data))
    if not found:
        raise FileNotFoundError(f"no verify_model_plans.py run_*.json in {directory}")
    _, _, path, data = max(found)
    return path, data


def summarize(plans: list[dict], reference: dict[int, str], verify: dict, metadata: dict | None,
              cohort: str) -> dict:
    predicted = {}
    for row in plans:
        if isinstance(row, dict) and type(row.get("case_id")) is int and isinstance(row.get("diagnosis"), str):
            predicted.setdefault(row["case_id"], row["diagnosis"].strip().lower())
    if cohort == "pilot":
        reference = {h: p for h, p in reference.items() if h in predicted}
    extra = sorted(set(predicted) - set(reference))
    if extra and cohort != "pilot":
        raise ValueError(f"{len(extra)} plan case IDs are outside the {cohort} cohort")
    return {
        "cohort": cohort,
        "generation": metadata,
        "diagnosis": diagnosis_metrics(predicted, reference),
        "plans": {k: verify.get(k) for k in VERIFY_KEYS},
        "verifier_evaluation": verify.get("evaluation"),
        "note": "Acceptance means compliance with rule catalog v2.1, not clinical correctness.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, type=Path, help="generated plans JSON list (case_id, diagnosis, ...)")
    ap.add_argument("--verify-dir", required=True, type=Path, help="directory holding verify_model_plans.py run_*.json")
    ap.add_argument("--cohort", choices=("pilot", "validation", "test"), default="validation")
    ap.add_argument("--generation-metadata", type=Path, help="default: <plans>.metadata.json if present")
    ap.add_argument("--facts-json", type=Path, help="case facts file; skips reading the dataset")
    ap.add_argument("--split-file", type=Path, help="alternate split JSON (synthetic tests); skips the frozen split")
    ap.add_argument("--out", type=Path, help="output directory (default: --verify-dir)")
    args = ap.parse_args(argv)

    plans = json.loads(args.plans.read_text())
    if not isinstance(plans, list):
        ap.error("plans file must contain a JSON list")
    meta_path = args.generation_metadata or args.plans.with_suffix(".metadata.json")
    metadata = json.loads(meta_path.read_text()) if meta_path.is_file() else None
    try:
        _, verify = latest_verify_run(args.verify_dir)
    except FileNotFoundError as err:
        ap.error(str(err))

    if args.cohort == "pilot":
        wanted = sorted({r["case_id"] for r in plans if isinstance(r, dict) and type(r.get("case_id")) is int})
    elif args.split_file is not None:
        splits = json.loads(args.split_file.read_text())["splits"]
        wanted = [int(h) for h in splits["test" if args.cohort == "test" else "val"]]
    else:
        from clinverify.eval.protocol import cohort_ids
        wanted = cohort_ids(args.cohort)
    if args.facts_json:
        facts = {int(k): v for k, v in json.loads(args.facts_json.read_text()).items()}
    else:
        from clinverify.data.case_loader import load_case_facts
        facts = load_case_facts(wanted)
    missing_facts = [h for h in wanted if h not in facts]
    if missing_facts:
        ap.error(f"{len(missing_facts)} cohort cases have no reference pathology")
    reference = {h: facts[h]["pathology"] for h in wanted}

    try:
        summary = summarize(plans, reference, verify, metadata, args.cohort)
    except ValueError as err:
        ap.error(str(err))
    out = args.out or args.verify_dir
    out.mkdir(parents=True, exist_ok=True)
    path = out / "evaluation_summary.json"
    path.write_text(json.dumps(summary, indent=1) + "\n")
    d, p = summary["diagnosis"], summary["plans"]
    print(f"diagnosis: n={d['n']} accuracy={d['accuracy']} macro_f1={d['macro_f1']} missing={d['n_missing']}")
    print(f"plans: checked_acceptance={p['supported_checked_acceptance_rate']} joint_success={p['joint_success_rate']} "
          f"status={p['status']}")
    print("summary:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
