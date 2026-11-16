"""Execute the Airflow DAG file with stub Airflow classes, so a NameError or a broken chain fails CI.

CI does not install Airflow, and a text check cannot see an undefined name; this runs the module for real.
"""
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
CHAIN = ["validation_only_guard", "data_manifest", "data_clean", "data_missing", "data_transform", "data_validate",
         "data_eda", "data_splits", "warehouse", "verifier_regression", "generate_plans", "verify_z3",
         "evaluate_harness", "g_eval", "report"]


class _Task:
    def __init__(self, task_id, bash_command="", env=None, **_):
        self.task_id, self.bash_command, self.env, self.downstream = task_id, bash_command, env or {}, []
        _DAG.current.tasks[task_id] = self

    def __rshift__(self, other):
        self.downstream.append(other)
        return other


class _DAG:
    current = None

    def __init__(self, dag_id, **kwargs):
        self.dag_id, self.kwargs, self.tasks = dag_id, kwargs, {}

    def __enter__(self):
        _DAG.current = self
        return self

    def __exit__(self, *exc):
        return False


def _load(monkeypatch):
    for name in ("airflow", "airflow.models", "airflow.providers", "airflow.providers.standard",
                 "airflow.providers.standard.operators"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    dag_mod = types.ModuleType("airflow.models.dag")
    dag_mod.DAG = _DAG
    bash_mod = types.ModuleType("airflow.providers.standard.operators.bash")
    bash_mod.BashOperator = _Task
    monkeypatch.setitem(sys.modules, "airflow.models.dag", dag_mod)
    monkeypatch.setitem(sys.modules, "airflow.providers.standard.operators.bash", bash_mod)
    spec = importlib.util.spec_from_file_location("clinverify_dag_under_test", ROOT / "dags/clinverify_pipeline.dag.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)            # raises on NameError and similar
    return module.dag


def test_dag_file_executes_and_chain_is_complete(monkeypatch):
    dag = _load(monkeypatch)
    assert dag.dag_id == "clinverify_pipeline"
    assert set(CHAIN) <= set(dag.tasks)
    for a, b in zip(CHAIN, CHAIN[1:]):
        assert dag.tasks[b] in dag.tasks[a].downstream, f"{a} >> {b} missing"


def test_model_steps_use_the_generated_plans_and_metadata(monkeypatch):
    t = _load(monkeypatch).tasks
    for task in ("verify_z3", "evaluate_harness", "g_eval"):
        assert '"$plans"' in t[task].bash_command, task
    assert "--generation-metadata" in t["verify_z3"].bash_command
    assert "catalog_labeled_plans" not in t["evaluate_harness"].bash_command
    assert '--ollama-host "$OLLAMA_HOST"' in t["generate_plans"].bash_command
    assert "--cohort validation" in t["generate_plans"].bash_command
