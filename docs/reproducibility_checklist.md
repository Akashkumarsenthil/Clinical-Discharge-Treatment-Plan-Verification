# Reproducibility checklist (Template 10.4)

**Status:** filled from the repository as of 2026-11-16 (local, no new runs).  
**Course rule:** any result that cannot be regenerated on request is treated as not obtained.  
**Related:** [metrics.md](metrics.md), [evaluation_protocol.json](evaluation_protocol.json), [README.md](../README.md), [baseline_notes.md](baseline_notes.md), [cloud_gpu.md](cloud_gpu.md).

| Item | Where it lives | Done |
|---|---|---|
| Pinned environment / dependency pins | [`requirements.txt`](../requirements.txt) (pipeline, Z3, warehouse, Streamlit). Optional training envs: [`requirements-training.txt`](../requirements-training.txt), [`requirements-training-cpu.txt`](../requirements-training-cpu.txt), [`requirements-training-cuda.txt`](../requirements-training-cuda.txt). CI: [`.github/workflows/tests.yml`](../.github/workflows/tests.yml) (Python 3.12). Prefer Python **3.12 or 3.13** (pandas 2.2.3 breaks on 3.14). | [x] |
| Seeds recorded for every reported run | Protocol generation seeds **298, 299, 300**; bootstrap seed **298** ([`evaluation_protocol.json`](evaluation_protocol.json)). Model A validation aggregates: seed **298**, temperature **0** ([`validation_summary.json`](validation_summary.json)). Baseline sample seed **298** ([`baseline_notes.md`](baseline_notes.md)). Metadata fields: `model`, `model_digest`, `prompt_sha256`, `seed`, `temperature`, `top_p`, `max_new_tokens`. | [x] |
| Experiment tracking: config, metrics, artifacts per run | Generation: `*.metadata.json` + `*.run.json` under local `results/model_runs/` (gitignored; counts only may be copied to docs). Aggregates committed: [`validation_summary.json`](validation_summary.json). Protocol + catalog versions recorded in run metadata / docs. Airflow cloud path: `results/model_runs/airflow_runs/<day>/…` on the VM. | [x] |
| Dataset versioning | MIMIC-IV **v3.1** + MIMIC-IV-Ext-CDM **v1.1** outside the repo (`MIMIC_DIR`, default `~/data/mimic`). Split **v2**: [`data/splits/ext_cdm_splits_v2.json`](../data/splits/ext_cdm_splits_v2.json). Protocol pins `split_sha256` = `0e83a970…2f2c` and `supported_test_ids_sha256` = `0b47751e…893e`. Integrity: `python scripts/data_demo.py manifest` vs PhysioNet `SHA256SUMS.txt`. | [x] |
| Documented hardware and runtime | **Local Model A / baseline:** NVIDIA RTX 5060 Ti 16 GB, WSL2; Ollama serving `qwen2.5:14b` (Q4_K_M); ~2,268 ms/case for validation generation (Workbook 2 notes). **Baseline:** Llama 3.1 8B 4-bit, 400 cases ([`baseline_notes.md`](baseline_notes.md)). **Cloud:** GCP VM `clinverify-airflow`, zone `us-west1-a`, g2-standard-4 + L4 when on GPU; auto-stop via DAG ([`airflow_cloud.md`](airflow_cloud.md), [`cloud_gpu.md`](cloud_gpu.md)). Mac (Apple Silicon): synthetic Quickstart + unit tests only for full clone checks; 14B batch runs are not required on 16 GB Mac. | [x] |
| README runnable by someone outside the team | [`README.md`](../README.md) Quickstart: venv, `pip install -r requirements.txt`, `pytest`, synthetic data, `data_demo.py`, `run_pipeline.py`, `run_eval.py`. Real MIMIC stays local / VM; never committed. | [x] |
| External team / fresh-clone run report | **Partial.** Ritika fresh clone on macOS 15.7.3, Python 3.12.2 and 3.13.7, 2026-11-04, commit `04acfc4`: Quickstart commands exit 0, **159 tests** pass (recorded in README and TM2 memo). No separate third-team formal report file yet; mark complete when another team submits Template §7 external report. | [~] |

`[x]` = present in repo/docs · `[~]` = partial · `[ ]` = missing

## How to reproduce the main committed checks (no PhysioNet)

```bash
git clone https://github.com/Akashkumarsenthil/Clinical-Discharge-Treatment-Plan-Verification.git
cd Clinical-Discharge-Treatment-Plan-Verification
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests
python scripts/make_synthetic_data.py --out ~/synthetic_mimic
MIMIC_DIR=~/synthetic_mimic python scripts/data_demo.py all
MIMIC_DIR=~/synthetic_mimic python scripts/run_pipeline.py
python scripts/run_eval.py --plans tests/data/catalog_labeled_plans.json --rules clinverify.rules.catalog
```

## How to reproduce Model A validation aggregates (credentialed machine)

1. Point `MIMIC_DIR` at Ext-CDM v1.1 + linked MIMIC-IV tables; confirm split file hash matches the protocol.
2. Pull `qwen2.5:14b` in local Ollama; host must be local (`127.0.0.1` / `localhost` / Docker host).
3. `python scripts/generate_model_a_plans.py --cohort validation --seed 298 --from-warehouse` (or Airflow `cloud_run.sh`).
4. Verify + summarize; compare rates to [`validation_summary.json`](validation_summary.json). Do not touch the test split until [`model_a_freeze_checklist.md`](model_a_freeze_checklist.md) is signed off.

## Still open for a stronger §7 claim

- Formal **external-team** clone report (beyond Ritika’s Quickstart note).
- Full freeze checklist ticks (team decisions on temperature / Model E status; eligibility; rule second review) before test-split regeneration.
- Per-run artifacts for cloud/Airflow stays on the VM unless aggregate-only exports are copied into `docs/`.

## One-line for the report

**Pinned requirements, protocol-hashed split v2, seeds 298–300, metadata on every generation, and a documented fresh-clone Quickstart (159 tests); external formal clone report still partial.**
