# Guideline RAG (A+RAG)

Code: [`src/clinverify/rag/`](../src/clinverify/rag/). Flag: `generate_model_a_plans.py --rag` (Airflow `rag=on`).

## What it does

1. **Corpus.** The public guideline text in [`data/guidelines/`](../data/guidelines/SOURCES.md) is cleaned (page
   navigation, author lists, reference entries and repeats dropped) and cut into passages of at most 1,000 characters:
   517 passages (SWE 192, ILATAM 173, KASID26 146, WSES25 4, ACG26 2).
2. **Index.** Each passage is embedded locally with `nomic-embed-text` (Ollama) and stored in
   `results/rag/guidelines.duckdb` (`rag_chunks`, `rag_meta`). The index is built on first use and rebuilt
   automatically if the corpus, the chunker or the embedding model digest changes. It holds guideline text only.
3. **Retrieval.** For each case, the first 4,000 characters of the record (history, exam, first labs) are embedded
   in memory as the query, and the top 3 passages by cosine similarity are retrieved. The query text and its
   embedding are never written to disk.
4. **Prompt.** The passages go in the user message before the record (`RAG_USER_TEMPLATE` in
   [`model_a.py`](../src/clinverify/models/model_a.py)); the system prompt, schema and generation settings are
   unchanged.

## What a run records

| File | Contents |
|---|---|
| `*.metadata.json` | same fields as A0; `prompt_sha256` also covers the RAG template, k, query length and index hash |
| `*.run.json` | `rag`: index hash, corpus hash, embed model and digest, k, query length |
| `*.rag.json` | per case: the IDs and scores of the passages retrieved (e.g. `SWE:0050`), no record text |

Without `--rag` the prompt hash is unchanged (`995be554…`), so A0 runs stay comparable. A base run and a RAG run
cannot share an output directory (the generator refuses mixed settings); Airflow writes them to separate folders.

## Caveats to report

- **Circularity.** The passages come from the same guidelines the Z3 rules were written from. A+RAG measures whether
  the model follows guideline text it is shown, not external clinical knowledge; any gain in checked acceptance
  under RAG partly reflects that overlap.
- **Coverage.** No cholecystitis guideline is in the corpus (the rule catalog cites none), and WSES25 and ACG26 are
  abstracts only, so appendicitis-complication and diverticulitis-colonoscopy guidance is thin.
- **Context length.** Three passages add up to about 1,000 tokens. The generator prints the largest prompt size and how many
  cases come close to `num_ctx` (8,192); check that line on the first validation run.

## Running

```bash
ollama pull nomic-embed-text
python scripts/generate_model_a_plans.py --cohort validation --seed 298 --from-warehouse --rag --out RUN_DIR
python scripts/generate_model_a_plans.py --cohort validation --dry-run --rag   # fake model and embedder
```

Options: `--rag-k` (default 3), `--rag-index`, `--embed-model` (default `nomic-embed-text`).
