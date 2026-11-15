# Four-way ablation table (Model A)

**Status:** A0 metrics filled from [`validation_summary.json`](validation_summary.json); other columns blank  
**Cohort:** validation (460) unless noted  
**Generator:** `scripts/generate_model_a_plans.py` · seed **298** (also 299/300 when reporting spread)  
**Judge:** frozen in [`geval_judge_freeze.md`](geval_judge_freeze.md) (`llama3.1:8b`)  
**Warehouse:** `--from-warehouse` after `run_pipeline`

## Variants

| Code | Meaning |
|---|---|
| **A0** | Base Model A (prompted), no RAG, no fine-tune |
| **A+RAG** | A0 + guideline retrieval (`--rag`) |
| **A+FT** | Fine-tuned Model A, no RAG |
| **A+RAG+FT** | Fine-tuned Model A + RAG |

## Results shell (validation)

Leave non-A0 cells blank until that variant’s run is frozen. Do not paste patient text here.

| Metric | A0 | A+RAG | A+FT | A+RAG+FT |
|---|---|---|---|---|
| Diagnosis accuracy | **0.887** (408/460) | | | |
| Checked acceptance | **0.146** (49/336 covered) | | | |
| Joint success | **0.120** | | | |
| G-Eval composite (mean) | *smoke only* **4.125** | | | |
| G-Eval n | *smoke* **2** (not 460) | | | |
| Notes / artifact path (local) | `docs/validation_summary.json` · Model A `qwen2.5:14b` seed 298; G-Eval smoke → `results/geval/smoke/` | | | |

A0 source: `validation_summary.json` → `models["Model A (qwen2.5:14b)"]` (accuracy 0.88696…, checked acceptance 0.14583…, joint success 0.11957…). G-Eval is **not** a full validation score — local smoke on 2 warehouse plans only ([`geval_judge_freeze.md`](geval_judge_freeze.md)).

Optional seed spread (mean ± sd across 298/299/300) — same columns, separate row block when ready.

## Circularity caveat (required in report)

RAG indexes **public guideline text** that the rule catalog already cites (e.g. WSES / ACG). The Z3 rules and the retrieved passages therefore share the same source family.

That means **A+RAG is not an independent external knowledge test**. Treat gains as:

- possible better *phrasing / coverage* of guideline-aligned plans, and/or  
- **circular** reinforcement of rules already encoded in the verifier  

Always state this caveat next to any A+RAG or A+RAG+FT claim. Do **not** claim that RAG proves generalization beyond the guideline set used to write the rules.

MIMIC notes are **not** in the RAG index.

## How to fill later

1. Trigger Airflow `clinverify_pipeline` four times with params:
   - A0 → `rag=off`, `model=base`
   - A+RAG → `rag=on`, `model=base` (blocked until RAG ships)
   - A+FT → `rag=off`, `model=ft`
   - A+RAG+FT → `rag=on`, `model=ft`
2. Or run warehouse → generate → Z3 → harness → G-Eval by hand with the same flags.  
3. Copy **aggregate** metrics only into the table.  
4. Keep raw plans / G-Eval JSON under `results/` (gitignored).  
5. If judge prompt or model changes, bump a table version note and link a new freeze doc.

## Related

- Metrics definitions: [`metrics.md`](metrics.md)  
- G-Eval freeze: [`geval_judge_freeze.md`](geval_judge_freeze.md)  
- Rule catalog: [`rule_catalog.md`](rule_catalog.md)  
