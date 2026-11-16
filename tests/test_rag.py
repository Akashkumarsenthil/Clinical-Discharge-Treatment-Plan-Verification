"""Guideline RAG: chunking, index, retrieval and the RAG prompt. Fake embedder only; no Ollama, no MIMIC."""
import json
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinverify import rag as R  # noqa: E402
from clinverify.models import model_a as A  # noqa: E402
from clinverify.rag import corpus as C  # noqa: E402

PROSE = "Antibiotic therapy alone is an acceptable first-line treatment for uncomplicated acute appendicitis in adults."


def write_corpus(tmp_path):
    d = tmp_path / "guidelines"
    d.mkdir()
    (d / "APP_test.txt").write_text(
        "# Citation: synthetic\n# Used by rules: R-APP-001\n- \n Menu\n"
        f"{PROSE}\n{PROSE}\n"
        "Smith J, et al. (2020) Appendicitis trial. doi:10.1000/xyz and Google Scholar link that is long enough here.\n"
        "Laparoscopic appendectomy remains the standard operative treatment when surgery is chosen for appendicitis.\n")
    (d / "PAN_test.txt").write_text(
        "Early oral feeding within 24 hours is recommended in mild acute pancreatitis when the patient tolerates it.\n"
        "Parenteral nutrition should be reserved for severe acute pancreatitis when enteral feeding is not possible.\n")
    return d


def test_clean_lines_drops_headers_navigation_references_and_repeats():
    lines = C.clean_lines(f"# header line that is long enough to keep if it were prose, but it is a header\n"
                          f"Menu\n{PROSE}\n  {PROSE}  \nSee doi:10.1/abc for the full trial report and methods.\n")
    assert lines == [PROSE]


def test_chunks_respect_the_size_limit_and_keep_all_text():
    lines = [f"Sentence number {i} about acute diverticulitis management and follow-up colonoscopy." for i in range(40)]
    lines.append("A very long line. " * 120)
    chunks = C.chunk_lines(lines, max_chars=300)
    assert all(len(c) <= 300 for c in chunks)
    joined = " ".join(chunks)
    assert all(line in joined for line in lines[:40])


def test_real_corpus_loads_with_stable_ids_and_hash():
    chunks = R.load_chunks()
    assert len(chunks) > 100
    assert {c.source for c in chunks} >= {"SWE", "ILATAM", "KASID26", "WSES25", "ACG26"}
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert R.corpus_sha256(chunks) == R.corpus_sha256(R.load_chunks())


def test_index_round_trip_and_topic_retrieval(tmp_path):
    chunks = C.load_chunks(write_corpus(tmp_path))
    path = tmp_path / "idx.duckdb"
    meta = R.build_index(R.HashEmbedder(), path, chunks)
    index = R.load_index(path)
    assert meta == index.meta and meta["n_chunks"] == len(chunks) == len(index.vectors)
    hits = R.retrieve(index, R.HashEmbedder(), {7: "mild acute pancreatitis oral feeding tolerated"}, k=2)
    assert [c.source for c, _ in hits[7]][0] == "PAN"
    assert hits == R.retrieve(index, R.HashEmbedder(), {7: "mild acute pancreatitis oral feeding tolerated"}, k=2)


def test_query_text_is_never_written_to_the_index(tmp_path):
    chunks = C.load_chunks(write_corpus(tmp_path))
    path = tmp_path / "idx.duckdb"
    R.build_index(R.HashEmbedder(), path, chunks)
    index = R.load_index(path)
    R.retrieve(index, R.HashEmbedder(), {1: "PRIVATE_RECORD_MARKER appendicitis"}, k=1)
    con = duckdb.connect(str(path), read_only=True)
    dump = json.dumps(con.execute("SELECT * FROM rag_chunks").fetchall() + con.execute("SELECT * FROM rag_meta").fetchall())
    con.close()
    assert "PRIVATE_RECORD_MARKER" not in dump


def test_open_index_rebuilds_when_the_embedder_changes(tmp_path):
    path = tmp_path / "idx.duckdb"
    first = R.open_index(R.HashEmbedder(dims=64), path)
    assert R.open_index(R.HashEmbedder(dims=64), path).meta == first.meta
    second = R.open_index(R.HashEmbedder(dims=128), path)
    assert second.meta["dims"] == 128 and second.meta["index_sha256"] != first.meta["index_sha256"]


def test_build_index_rejects_a_bad_embedder(tmp_path):
    class Short(R.HashEmbedder):
        def embed(self, texts):
            return super().embed(texts)[:-1]

    with pytest.raises(ValueError):
        R.build_index(Short(), tmp_path / "idx.duckdb", C.load_chunks(write_corpus(tmp_path)))


def test_prompt_hash_unchanged_without_rag_and_covers_rag_settings():
    base = A.prompt_sha256()
    assert base == A.prompt_sha256(None)
    a = A.prompt_sha256({"index_sha256": "x", "k": 3})
    assert a != base and a != A.prompt_sha256({"index_sha256": "x", "k": 4})


def test_generate_plans_uses_rag_template_only_with_guidance(tmp_path):
    seen = []

    class Client:
        def chat(self, system, user, **kw):
            seen.append(user)
            return {"message": {"content": json.dumps({"diagnosis": "appendicitis", "treatments": [],
                                                       "postop_antibiotic_days": None})}}

    A.generate_plans(Client(), {1: "REC1"}, [1], tmp_path / "a.jsonl")
    A.generate_plans(Client(), {1: "REC1"}, [1], tmp_path / "b.jsonl", guidance={1: "[1] (SWE) passage"})
    assert seen[0] == A.USER_TEMPLATE.format(case_id=1, record="REC1")
    assert seen[1].startswith("Excerpts from published clinical guidelines") and "[1] (SWE) passage" in seen[1]
    assert seen[1].endswith(A.USER_TEMPLATE.format(case_id=1, record="REC1"))
