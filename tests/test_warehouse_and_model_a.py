"""Warehouse pipeline and Model A plumbing on synthetic data (no patient data, no LLM: the server is stubbed)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("duckdb")

from clinverify import warehouse as W  # noqa: E402
from clinverify.data import ext_cdm as E  # noqa: E402
from clinverify.data import splits as S  # noqa: E402
from clinverify.data.synthetic import generate  # noqa: E402
from clinverify.models import model_a as A  # noqa: E402


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    root = tmp_path_factory.mktemp("synthetic_mimic")
    generate(root, n_cases=200)
    ext, mimic_iv = root / "mimic-iv-ext-cdm-1.1", root / "physionet.org" / "files" / "mimiciv" / "3.1"
    cases = E.case_table(E.load_pathology_ids(ext))
    splits = S.make_grouped_splits(cases, E.subject_map(mimic_iv), n_test=40)
    split_file = root / "splits.json"
    split_file.write_text(json.dumps({"splits": {k: [int(h) for h in v] for k, v in splits.items()}}))
    return {"ext": ext, "mimic_iv": mimic_iv, "split_file": split_file, "db": root / "wh.duckdb"}


def run(synth, **kw):
    return W.run_pipeline(synth["db"], synth["ext"], synth["mimic_iv"], synth["split_file"], **kw)


def test_pipeline_builds_layers_and_passes_checks(synth):
    out = run(synth)
    assert out["status"] == "ok" and out["n_checks_failed"] == 0 and out["n_cases"] == 200
    con = W.connect(synth["db"])
    layers = W.layer_counts(con)
    assert {"raw", "staging", "mart", "ops"} <= set(layers["layer"])
    assert con.execute("SELECT COUNT(*) FROM mart.cases").fetchone()[0] == 200


def test_failed_raw_check_publishes_nothing(synth):
    run(synth)
    con = W.connect(synth["db"])
    before = con.execute('SELECT COUNT(*) FROM raw."history_of_present_illness"').fetchone()[0]
    con.close()
    bad = run(synth, inject_fault=True)
    assert bad["status"] == "failed_checks" and bad["checks"]["status"].eq("fail").any()
    con = W.connect(synth["db"])
    assert con.execute('SELECT COUNT(*) FROM raw."history_of_present_illness"').fetchone()[0] == before
    assert W.run_history(con, limit=1)["status"].iloc[0] == "failed_checks"


def test_model_input_never_contains_the_answer(synth):
    tables = E.load_tables(synth["ext"])
    cleaned, _ = E.clean_tables(tables)
    transformed = E.transform_tables(cleaned, synth["ext"])
    inputs = A.case_inputs(transformed)
    assert len(inputs) == 200
    dx = transformed["discharge_diagnosis"].set_index("hadm_id")["discharge_diagnosis"]
    leaked = [h for h, text in inputs.items() if dx[h] and dx[h] in text]
    assert not leaked
    assert all("DISCHARGE" not in text and "ICD" not in text for text in inputs.values())


def test_parse_plan_and_prompt_hash():
    plan = A.parse_plan(7, '{"diagnosis": "appendicitis", "treatments": ["appendectomy", "appendectomy"], "postop_antibiotic_days": 0}')
    assert plan == {"case_id": 7, "diagnosis": "appendicitis", "treatments": ["appendectomy"], "postop_antibiotic_days": 0}
    with pytest.raises(ValueError):
        A.parse_plan(7, '{"diagnosis": "gastritis", "treatments": []}')
    h = A.prompt_sha256()
    assert len(h) == 64 and h == A.prompt_sha256()


class StubOllama:
    """Answers like the Ollama /api/chat endpoint; case 2 returns broken JSON."""
    def __init__(self):
        self.calls = 0

    def chat(self, system, user, **kw):
        self.calls += 1
        assert kw["schema"] is A.PLAN_SCHEMA and kw["seed"] == 298
        broken = "case 2)" in user
        content = "{not json" if broken else '{"diagnosis": "pancreatitis", "treatments": [], "postop_antibiotic_days": null}'
        return {"message": {"content": content}, "prompt_eval_count": 100, "eval_count": 20}


def test_generation_is_resumable_and_drops_failures(tmp_path):
    client, out = StubOllama(), tmp_path / "plans.jsonl"
    inputs = {1: "record one", 2: "record two", 3: "record three"}
    log = A.generate_plans(client, inputs, [1, 2], out, progress_every=0)
    assert log["ok"].tolist() == [True, False] and log["error"].iloc[1] == "JSONDecodeError"
    A.generate_plans(client, inputs, [1, 2, 3], out, progress_every=0)
    assert client.calls == 3                                   # cases 1 and 2 were not generated twice
    assert [p["case_id"] for p in A.load_plans(out)] == [1, 3]  # the failed case is left out, never retried
