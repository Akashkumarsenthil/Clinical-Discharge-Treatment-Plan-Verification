"""End-to-end pipeline on synthetic MIMIC with a stub Ollama. No patient data and no live model."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("duckdb")

from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data import splits as S  # noqa: E402
from clinverify.data.synthetic import generate  # noqa: E402

PY = sys.executable
PLAN = '{"diagnosis": "appendicitis", "treatments": ["appendectomy", "preoperative_antibiotic"], "postop_antibiotic_days": 0}'


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send({"models": [{"name": "qwen2.5:14b", "model": "qwen2.5:14b", "digest": "synthetic-digest"}]})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        data = json.loads(raw.decode() or "{}")
        messages = data.get("messages") or []
        text = messages[-1].get("content", "") if messages else ""
        content = "4" if "single integer" in text else PLAN
        self._send({"message": {"content": content}, "prompt_eval_count": 12, "eval_count": 6})


@pytest.fixture(scope="module")
def ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host = f"http://127.0.0.1:{server.server_address[1]}"
    yield host
    server.shutdown()


def _run(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=ROOT, env=env, capture_output=True, text=True)


def test_dag_matches_ta_checklist():
    text = (ROOT / "dags" / "clinverify_pipeline.dag.py").read_text()
    assert "{{ ds }}" not in text
    assert "logical_date" in text
    assert "scripts/generate_model_a_plans.py" in text
    assert "scripts/data_demo.py" in text
    assert "scripts/run_eval.py" in text
    assert "validation_only_guard" in text
    assert 'COHORT = "validation"' in text
    for task in (
        "data_manifest", "data_clean", "data_missing", "data_transform", "data_validate",
        "data_eda", "data_splits", "warehouse", "generate_plans", "verify_z3",
        "evaluate_harness", "g_eval", "report",
    ):
        assert task in text
    assert (ROOT / "docker-compose.yml").is_file()
    retired = (ROOT / "scripts" / "scheduled_pipeline.sh").read_text()
    assert "RETIRED" in retired
    assert "clinverify_pipeline.dag.py" in retired
    assert "exit 2" in retired


def test_warehouse_generate_verify_geval(tmp_path, ollama):
    mimic = tmp_path / "mimic"
    generate(mimic, n_cases=80)
    ext = mimic / "mimic-iv-ext-cdm-1.1"
    mimic_iv = mimic / "physionet.org" / "files" / "mimiciv" / "3.1"
    cases = E.case_table(E.load_pathology_ids(ext))
    splits = S.make_grouped_splits(cases, E.subject_map(mimic_iv), n_test=16)
    split_file = tmp_path / "splits.json"
    split_file.write_text(json.dumps({"splits": {k: [int(h) for h in v] for k, v in splits.items()}}))

    env = os.environ.copy()
    env["MIMIC_DIR"] = str(mimic)
    env["OLLAMA_HOST"] = ollama
    out = tmp_path / "run"

    warehouse = _run(
        ["scripts/run_pipeline.py", "--db", str(tmp_path / "wh.duckdb"), "--split-file", str(split_file), "--trigger", "integration"],
        env,
    )
    assert warehouse.returncode == 0, warehouse.stderr
    assert '"status": "ok"' in warehouse.stdout

    generated = _run(
        [
            "scripts/generate_model_a_plans.py",
            "--cohort", "validation",
            "--seed", "298",
            "--limit", "2",
            "--split-file", str(split_file),
            "--out", str(out),
            "--ollama-model", "qwen2.5:14b",
            "--ollama-host", ollama,
        ],
        env,
    )
    assert generated.returncode == 0, generated.stderr
    plans = out / "model_a_qwen2.5_14b_val_seed298.json"
    rows = json.loads(plans.read_text())
    assert len(rows) == 2
    assert {row["diagnosis"] for row in rows} == {"appendicitis"}

    verified = _run(
        ["scripts/verify_model_plans.py", "--plans", str(plans), "--cohort", "pilot", "--out", str(tmp_path / "verify")],
        env,
    )
    assert verified.returncode == 0, verified.stderr
    assert '"n_plans": 2' in verified.stdout

    judged = _run(
        ["scripts/run_geval.py", "--plans", str(plans), "--judge-model", "llama3.1:8b", "--out", str(tmp_path / "geval")],
        env,
    )
    assert judged.returncode == 0, judged.stderr
    assert "composite mean=" in judged.stdout
