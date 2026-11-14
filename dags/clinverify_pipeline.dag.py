"""ClinVerify Airflow DAG (TA checklist §3): data → warehouse → model → judge → report.

Replaces Windows Task Scheduler / scripts/scheduled_pipeline.sh.
Run Airflow on a local machine or GCP VM (Docker Compose). Do not use Cloud Composer.

Hard rule: every model/eval step is validation-split only. The held-out test cohort
is never selected by this DAG.

Requires Airflow 3.x (schedule= not schedule_interval=).
Airflow Variables:
    MIMIC_DIR  – path to the MIMIC root on the worker (required)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow.models.dag import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Local standalone: DAG lives in <repo>/dags → parents[1] is the repo.
# Docker Compose on the GCP VM: set CLINVERIFY_REPO=/opt/clinverify (mounted RW).
_REPO_DEFAULT = str(Path(__file__).resolve().parents[1])
REPO = os.environ.get("CLINVERIFY_REPO", _REPO_DEFAULT)

_venv_python = os.path.join(REPO, ".venv", "bin", "python")
PYTHON = os.environ.get(
    "CLINVERIFY_PYTHON",
    _venv_python if Path(_venv_python).exists() else "python",
)

# Never change this to "test" in the DAG. The guard task refuses anything else.
COHORT = "validation"

RUN_DAY = (
    "{% if dag_run.logical_date %}"
    "{{ dag_run.logical_date.strftime('%Y-%m-%d') }}"
    "{% else %}"
    "{{ macros.datetime.utcnow().strftime('%Y-%m-%d') }}"
    "{% endif %}"
)
RESULTS_DIR = os.path.join(REPO, "results", "model_runs", "airflow_runs", RUN_DAY)
PLANS_JSON = os.path.join(RESULTS_DIR, "model_a_qwen2.5_14b_val_seed298.json")
REPORT_JSON = os.path.join(RESULTS_DIR, "pipeline_report.json")

TASK_ENV = {
    "MIMIC_DIR": "{{ var.value.get('MIMIC_DIR', '') }}",
    "PATH": os.environ.get("PATH", ""),
    "CLINVERIFY_COHORT": COHORT,
    "OLLAMA_HOST": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
    "PYTHONPATH": os.path.join(REPO, "src"),
}

default_args = {
    "owner": "sneha",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _bash(cmd: str) -> str:
    return f"cd {REPO!r} && {cmd}"


def _py(script_and_args: str) -> str:
    return _bash(f"{PYTHON!r} {script_and_args}")


with DAG(
    dag_id="clinverify_pipeline",
    description="ETL + warehouse + Model A (validation only) + Z3 + harness + G-Eval",
    schedule="0 2 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["clinverify", "pipeline", "validation-only"],
    params={"cohort": COHORT},
) as dag:

    validation_only_guard = BashOperator(
        task_id="validation_only_guard",
        bash_command=(
            "test \"{{ params.cohort }}\" = 'validation' || "
            "{ echo 'refusing non-validation cohort; this DAG is validation-split-only' >&2; exit 1; }"
        ),
        env=TASK_ENV,
    )

    data_manifest = BashOperator(task_id="data_manifest", bash_command=_py("scripts/data_demo.py manifest"), env=TASK_ENV)
    data_clean = BashOperator(task_id="data_clean", bash_command=_py("scripts/data_demo.py clean"), env=TASK_ENV)
    data_missing = BashOperator(task_id="data_missing", bash_command=_py("scripts/data_demo.py missing"), env=TASK_ENV)
    data_transform = BashOperator(task_id="data_transform", bash_command=_py("scripts/data_demo.py transform"), env=TASK_ENV)
    data_validate = BashOperator(task_id="data_validate", bash_command=_py("scripts/data_demo.py validate"), env=TASK_ENV)
    data_eda = BashOperator(task_id="data_eda", bash_command=_py("scripts/data_demo.py eda"), env=TASK_ENV)
    data_splits = BashOperator(task_id="data_splits", bash_command=_py("scripts/data_demo.py splits"), env=TASK_ENV)

    warehouse = BashOperator(
        task_id="warehouse",
        bash_command=_py("scripts/run_pipeline.py --trigger airflow"),
        env=TASK_ENV,
    )

    generate_plans = BashOperator(
        task_id="generate_plans",
        bash_command=(
            f"mkdir -p {RESULTS_DIR!r} && "
            + _py(
                "scripts/generate_model_a_plans.py "
                f"--cohort {COHORT} --seed 298 --out {RESULTS_DIR!r}"
            )
        ),
        env=TASK_ENV,
    )
    verify_z3 = BashOperator(
        task_id="verify_z3",
        bash_command=_py(
            f"scripts/verify_model_plans.py --plans {PLANS_JSON!r} --cohort {COHORT} --out {RESULTS_DIR!r}"
        ),
        env=TASK_ENV,
    )
    evaluate_harness = BashOperator(
        task_id="evaluate_harness",
        bash_command=_py(
            "scripts/run_eval.py "
            "--plans tests/data/catalog_labeled_plans.json "
            "--rules clinverify.rules.catalog --seed 298 "
            f"--out {RESULTS_DIR!r}"
        ),
        env=TASK_ENV,
    )

    g_eval = BashOperator(
        task_id="g_eval",
        bash_command=_py(
            f"scripts/run_geval.py --plans {PLANS_JSON!r} --judge-model llama3.1:8b --out {RESULTS_DIR!r}"
        ),
        env=TASK_ENV,
    )

    report = BashOperator(
        task_id="report",
        bash_command=_bash(
            f"{PYTHON!r} - <<'PY'\n"
            "import json\n"
            "from pathlib import Path\n"
            f"out = Path({RESULTS_DIR!r})\n"
            "plans = out / 'model_a_qwen2.5_14b_val_seed298.json'\n"
            "report = {\n"
            "  'cohort': 'validation',\n"
            "  'results_dir': str(out),\n"
            "  'plans_file': str(plans) if plans.exists() else None,\n"
            "  'n_plans': len(json.loads(plans.read_text())) if plans.exists() else 0,\n"
            "  'artifacts': sorted(p.name for p in out.glob('*') if p.is_file()),\n"
            "}\n"
            f"path = Path({REPORT_JSON!r})\n"
            "path.parent.mkdir(parents=True, exist_ok=True)\n"
            "path.write_text(json.dumps(report, indent=1) + '\\n')\n"
            "print(json.dumps(report, indent=1))\n"
            "PY"
        ),
        env=TASK_ENV,
    )

    validation_only_guard >> data_manifest >> data_clean >> data_missing >> data_transform
    data_transform >> data_validate >> data_eda >> data_splits >> warehouse
    warehouse >> generate_plans >> verify_z3 >> evaluate_harness >> g_eval >> report
