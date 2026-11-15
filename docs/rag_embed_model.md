# RAG embed model (plan §2 prep)

**Status:** frozen tag for upcoming `src/clinverify/rag/`  
**Date:** 2026-11-14  
**Owner:** Sneha

| Setting | Value |
|---|---|
| Ollama model | `nomic-embed-text` |
| Role | Embed public guideline chunks only (no MIMIC) |
| Local | Pulled 2026-11-14 (`ollama pull nomic-embed-text`) |
| Cloud VM | Same pull after Ollama install (see `docs/airflow_cloud.md`) |

Do not switch embed models mid-ablation without a new freeze note and a rebuilt DuckDB RAG index.

Guideline text to embed (collected, no MIMIC): [`data/guidelines/`](../data/guidelines/SOURCES.md).
