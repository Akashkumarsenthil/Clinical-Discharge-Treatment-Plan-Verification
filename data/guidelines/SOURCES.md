# Guideline corpus for RAG (§6 first bullet)

**Status:** collected 2026-11-14  
**Scope:** public guideline text cited by rule catalog v2.1 only  
**Forbidden:** MIMIC / any patient record text

## Files

| File | Catalog | Access in corpus | License / note |
|---|---|---|---|
| `SWE_salo_2025_bjs_open_zrae165.txt` | SWE | OA full text (PMC) | BJS Open / PMC (typically CC BY) |
| `WSES25_podda_2026_jama_surg_abstract.txt` | WSES25 | **Abstract only** | JAMA paywalled full text |
| `ILATAM_cardenas_2026_uegj_e70190.txt` | ILATAM | OA full text (PMC) | CC BY-NC-ND 4.0 |
| `ACG26_peery_2026_am_j_gastroenterol_abstract.txt` | ACG26 | **Abstract only** (PubMed) | AJG paywalled full text |
| `KASID26_lee_2026_intest_res.txt` | KASID26 | OA full text (journal HTML) | CC BY-NC 4.0 |

## Rule coverage

| Rule | Primary corpus file(s) |
|---|---|
| R-APP-001, R-APP-002 | SWE |
| R-APP-003 | WSES25 (abstract) |
| R-PAN-001 … R-PAN-005 | ILATAM |
| R-DIV-001 | ACG26 abstract + KASID26 |
| R-DIV-002, R-DIV-003 | ACG26 abstract (+ KASID26 colonoscopy recs) |

## Circularity

These are the **same** sources the Z3 rules were written from. RAG over this corpus is not an external knowledge test — see `docs/four_way_ablation_table.md`.

## Next (not this task)

Chunk + embed with `nomic-embed-text` into DuckDB under `src/clinverify/rag/`.
