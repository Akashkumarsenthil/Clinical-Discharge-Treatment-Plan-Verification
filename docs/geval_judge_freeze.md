# G-Eval judge freeze (smoke)

**Status:** frozen for local smoke / four-way table work  
**Date:** 2026-11-14  
**Owner:** Sneha

## Locked settings

| Setting | Value |
|---|---|
| Judge model | `llama3.1:8b` (local Ollama only) |
| Temperature | `0` |
| Criteria | coherence, relevance, fluency, groundedness (1–5) |
| Prompt template | `SCORE_PROMPT` + `CRITERIA` in `src/clinverify/eval/geval.py` |
| CLI | `scripts/run_geval.py` (default `--judge-model llama3.1:8b`) |

Do **not** change the judge prompt, criteria text, or default model without a new freeze note and a new four-way table column version. MIMIC / clinical notes must never go to a hosted API.

## Smoke evidence (no patient text)

- Plans: warehouse smoke, 2 validation cases (`qwen2.5:14b`, seed 298)
- Command: `python scripts/run_geval.py --plans …/warehouse_smoke/…json --judge-model llama3.1:8b --limit 2`
- Result (2026-11-15 UTC): `n=2`, composite mean **4.125** (min 3.75, max 4.5)
- Per-criterion means: coherence 4, relevance 4, fluency 4, groundedness 4.5
- Artifact path (local only): `results/geval/smoke/`

Full 460-case G-Eval waits for cloud Ollama / GPU; this smoke locks the judge contract.

Four-way results shell (A0 / A+RAG / A+FT / A+RAG+FT) and RAG circularity caveat: [`four_way_ablation_table.md`](four_way_ablation_table.md).
