"""Run G-Eval (LLM-as-judge) over a batch of model plans.

Scores each plan on 4 criteria (coherence, relevance, fluency, groundedness)
using a local Ollama judge. MIMIC text never leaves the machine.

Usage:
    # Score the first 10 plans with default judge (llama3.1:8b):
    python scripts/run_geval.py --plans path/to/plans.json --limit 10

    # Full validation run:
    python scripts/run_geval.py --plans path/to/plans.json

    # Different judge model:
    python scripts/run_geval.py --plans path/to/plans.json --judge-model qwen2.5:14b

Plans file: a JSON list of {"case_id", "diagnosis", "treatments", "postop_antibiotic_days"}
(the same format accepted by verify_model_plans.py).

Requires:
    - Local Ollama running with the judge model pulled
    - MIMIC_DIR set or ~/data/mimic present (for clinical context)

Output: results/geval/<timestamp>_<plans_stem>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify.data import ext_cdm as E          # noqa: E402
from clinverify.eval.geval import batch_score, summarise  # noqa: E402
from clinverify.models.model_a import case_inputs  # noqa: E402


def render_plan(plan: dict) -> str:
    """Render a structured plan dict as human-readable text for the judge LLM."""
    treatments = ", ".join(plan.get("treatments") or []) or "none"
    days = plan.get("postop_antibiotic_days")
    postop = f"{days} day(s)" if days is not None else "not applicable (no surgery planned)"
    return (
        f"Diagnosis: {plan.get('diagnosis', 'unknown')}\n"
        f"Treatments: {treatments}\n"
        f"Post-operative antibiotic days: {postop}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plans", required=True, type=Path,
                    help="JSON list of model plan dicts (same format as verify_model_plans.py)")
    ap.add_argument("--judge-model", default="llama3.1:8b",
                    help="Ollama model to use as judge (default: llama3.1:8b)")
    ap.add_argument("--timeout", type=int, default=120,
                    help="per-criterion Ollama timeout in seconds (default: 120)")
    ap.add_argument("--limit", type=int, default=None,
                    help="score only the first N plans (for quick sanity checks)")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "geval")
    args = ap.parse_args()

    plans = json.loads(args.plans.read_text())
    if not isinstance(plans, list):
        ap.error("plans file must be a JSON list")
    if args.limit:
        plans = plans[: args.limit]

    case_ids = [p["case_id"] for p in plans if isinstance(p.get("case_id"), int)]
    print(f"Loading clinical context for {len(case_ids)} cases from {E.EXT_CDM_DIR} ...")
    try:
        raw, _ = E.clean_tables(E.load_tables())
        raw.pop("lab_test_mapping", None)
        contexts = case_inputs(E.transform_tables(raw), hadm_ids=case_ids)
    except Exception as exc:
        print(f"ERROR loading CDM tables: {exc}", file=sys.stderr)
        print("Hint: set MIMIC_DIR or ensure ~/data/mimic/mimic-iv-ext-cdm-1.1/ exists.", file=sys.stderr)
        return 1

    batch = []
    missing_ctx = 0
    for plan in plans:
        cid = plan.get("case_id")
        ctx = contexts.get(int(cid), "") if isinstance(cid, int) else ""
        if not ctx:
            missing_ctx += 1
        batch.append({"plan_text": render_plan(plan), "case_context": ctx, "case_id": cid})

    if missing_ctx:
        print(f"Warning: {missing_ctx} case(s) had no clinical context (unsupported diagnosis or missing data).")

    print(f"Scoring {len(batch)} plans with judge={args.judge_model!r} ...")
    results = batch_score(batch, judge_model=args.judge_model, timeout=args.timeout)

    summary = summarise(results)
    print(f"\n=== G-Eval summary (judge: {args.judge_model}) ===")
    print(f"  n={summary['n']}  composite mean={summary['mean']}  "
          f"min={summary['min']}  max={summary['max']}")
    if summary.get("per_criterion"):
        for crit, score in summary["per_criterion"].items():
            print(f"  {crit}: {score}")

    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"geval_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{args.plans.stem}"
    out_path = args.out / f"{stem}.json"
    out_path.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "plans_file": str(args.plans),
        "judge_model": args.judge_model,
        "n_plans": len(plans),
        "summary": summary,
        "per_case": results,
    }, indent=1))
    print(f"\nResults written to: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
