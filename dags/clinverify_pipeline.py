"""Nightly Airflow DAG: warehouse refresh → plan generation → Z3 verification → G-Eval.

Requires Airflow 3.x (schedule= not schedule_interval=).
Run the warehouse and generation steps as BashOperators so they use the same
venv and MIMIC_DIR that the scripts expect.  G-Eval and verification run after
plan generation completes; they receive the generated .json path via XCom.

Environment variables that must be set in Airflow (Connections / Variables or
the worker environment):
    MIMIC_DIR        – path to the MIMIC root on the worker machine
    CLINVERIFY_REPO  – absolute path to this repository (default: DAG file location's parent)

Schedule: 02:00 UTC every day.  Catchup disabled so a restart doesn't replay old dates.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow.models.dag import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Repo root is two levels up from dags/
REPO = str(Path(__file__).resolve().parents[1])
VENV = os.path.join(REPO, ".venv", "bin", "python")
RESULTS_DIR = os.path.join(REPO, "results", "model_runs", "airflow_runs", "{{ ds }}")

# Output stem mirrors generate_model_a_plans.py naming: model_a_<tag>_val_seed298.json
# We use qwen2.5:14b → tag becomes "qwen2.5_14b" after re.sub
PLANS_JSON = os.path.join(RESULTS_DIR, "model_a_qwen2.5_14b_val_seed298.json")

default_args = {
    "owner": "sneha",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="clinverify_pipeline",
    description="Warehouse refresh, plan generation, Z3 verification, G-Eval",
    schedule="0 2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["clinverify", "pipeline"],
) as dag:

    warehouse_refresh = BashOperator(
        task_id="warehouse_refresh",
        bash_command=(
            f"cd {REPO!r} && "
            f"{VENV!r} scripts/run_pipeline.py --trigger airflow"
        ),
        env={"MIMIC_DIR": "{{ var.value.get('MIMIC_DIR', '') }}", "PATH": os.environ.get("PATH", "")},
    )

    generate_plans = BashOperator(
        task_id="generate_plans",
        bash_command=(
            f"mkdir -p {RESULTS_DIR!r} && "
            f"cd {REPO!r} && "
            f"{VENV!r} scripts/generate_model_a_plans.py "
            f"--cohort validation --seed 298 --out {RESULTS_DIR!r}"
        ),
        env={"MIMIC_DIR": "{{ var.value.get('MIMIC_DIR', '') }}", "PATH": os.environ.get("PATH", "")},
    )

    verify_plans = BashOperator(
        task_id="verify_plans",
        bash_command=(
            f"cd {REPO!r} && "
            f"{VENV!r} scripts/verify_model_plans.py "
            f"--plans {PLANS_JSON!r} --cohort validation"
        ),
        env={"MIMIC_DIR": "{{ var.value.get('MIMIC_DIR', '') }}", "PATH": os.environ.get("PATH", "")},
    )

    run_geval = BashOperator(
        task_id="run_geval",
        bash_command=(
            f"cd {REPO!r} && "
            f"{VENV!r} scripts/run_geval.py "
            f"--plans {PLANS_JSON!r} --judge-model llama3.1:8b "
            f"--out {RESULTS_DIR!r}"
        ),
        env={"MIMIC_DIR": "{{ var.value.get('MIMIC_DIR', '') }}", "PATH": os.environ.get("PATH", "")},
    )

    warehouse_refresh >> generate_plans >> verify_plans >> run_geval
