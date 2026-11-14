# Local Airflow Setup for ClinVerify Pipeline

Each team member who wants to run the automated pipeline locally must complete
this one-time setup. The pipeline runs entirely on your machine — no MIMIC data
leaves the box (PhysioNet DUA requirement).

## Prerequisites

- Anaconda (Python 3.13) installed — Airflow 3.1.0 ships with the conda env
- MIMIC-IV data downloaded to your machine (requires your own PhysioNet credentials)
- Ollama running locally with `qwen2.5:14b` and `llama3.1:8b` pulled

## 1. Confirm Airflow is available

```bash
airflow version   # should print 3.1.0
```

If not found, Airflow is in Anaconda:

```bash
/opt/anaconda3/bin/airflow version
```

## 2. Initialise the Airflow database (first time only)

```bash
airflow db migrate
```

## 3. Symlink the DAG into Airflow's dags folder

```bash
mkdir -p ~/airflow/dags
ln -sf "$(pwd)/dags/clinverify_pipeline.dag.py" ~/airflow/dags/clinverify_pipeline.dag.py
```

Run from the repo root. The symlink means any `git pull` update to the DAG
file is picked up by Airflow automatically — no re-copy needed.

Verify:

```bash
ls -la ~/airflow/dags/
```

## 4. Set your MIMIC_DIR variable in Airflow

The pipeline scripts read `MIMIC_DIR` to find your local MIMIC data.
**This step is required** — if unset the variable resolves to an empty string and
`warehouse_refresh` fails with `FileNotFoundError`.

```bash
airflow variables set MIMIC_DIR /path/to/your/mimic
# e.g. airflow variables set MIMIC_DIR ~/data/mimic
```

Verify it was saved:

```bash
airflow variables get MIMIC_DIR
```

## 5. Start Airflow (standalone mode)

Airflow 3.x requires the API server, scheduler, and worker to all be running.
`standalone` starts everything in one command:

```bash
airflow standalone
```

Wait for the line:

```
standalone | Airflow is ready
```

Keep this terminal open — it is your live log stream.

## 6. Register and unpause the DAG

In a second terminal:

```bash
airflow dags reserialize
airflow dags unpause clinverify_pipeline
airflow dags list | grep clinverify   # is_paused should be False
```

## 7. Trigger a manual run

```bash
airflow dags trigger clinverify_pipeline
```

Watch progress:

```bash
airflow tasks states-for-dag-run clinverify_pipeline <run_id>
# run_id from: airflow dags list-runs clinverify_pipeline
```

Or open the UI at `http://localhost:8080` (standalone starts the webserver).

## Pipeline task chain

Canonical DAG file: `dags/clinverify_pipeline.dag.py` (TA checklist §3).
Every model/eval step is **validation-split only**.

```
validation_only_guard
  → data_manifest → data_clean → data_missing → data_transform
  → data_validate → data_eda → data_splits → warehouse
  → generate_plans → verify_z3 → evaluate_harness → g_eval → report
```

| Task | Script | Fails if |
|------|--------|----------|
| `validation_only_guard` | built-in check | cohort is not `validation` |
| `data_*` | `scripts/data_demo.py <step>` | MIMIC_DIR wrong / tables missing |
| `warehouse` | `scripts/run_pipeline.py --trigger airflow` | MIMIC_DIR wrong / DuckDB locked |
| `generate_plans` | `scripts/generate_model_a_plans.py --cohort validation --seed 298` | Ollama not running / qwen2.5:14b not pulled |
| `verify_z3` | `scripts/verify_model_plans.py --plans <json> --cohort validation` | Generated plans file missing |
| `evaluate_harness` | `scripts/run_eval.py` (catalog labeled plans) | catalog / labeled plans missing |
| `g_eval` | `scripts/run_geval.py --judge-model llama3.1:8b` | llama3.1:8b not pulled |
| `report` | writes `pipeline_report.json` | results dir missing |

`scripts/scheduled_pipeline.sh` and Windows Task Scheduler are **retired**. Use Airflow.
For a GCP VM deploy package see `docker-compose.yml` and **`docs/airflow_cloud.md`**
(shared team UI login: **admin** / **admin**).

## Scheduled runs

The DAG runs nightly at **02:00 UTC** when Airflow standalone is running.
If your machine is off or Airflow is stopped, the missed run is skipped
(`catchup=False` in the DAG).

## Outputs

All run artifacts go to `results/model_runs/airflow_runs/<YYYY-MM-DD>/`
(gitignored — patient data never committed).
