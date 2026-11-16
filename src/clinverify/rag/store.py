"""Embed guideline passages with a local Ollama model, keep them in DuckDB, and retrieve the top-k for a case.

Only public guideline passages are stored. A case record is embedded in memory as the retrieval query and is never
written anywhere; what a run keeps per case is the IDs and scores of the passages it retrieved.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import duckdb

from clinverify.rag.corpus import ROOT, Chunk, corpus_sha256, load_chunks

DEFAULT_INDEX = ROOT / "results" / "rag" / "guidelines.duckdb"
DEFAULT_EMBED_MODEL = "nomic-embed-text"     # frozen in docs/rag_embed_model.md
DEFAULT_K = 3
QUERY_CHARS = 4000        # leading part of the record (history, exam, first labs) used as the query
# nomic-embed-text is trained with task prefixes; documents and queries need different ones.
DOC_PREFIX, QUERY_PREFIX = "search_document: ", "search_query: "


class Embedder(Protocol):
    model: str

    def digest(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class OllamaEmbedder:
    """Local Ollama /api/embed client. The host must already be checked with model_a.local_ollama_host."""

    def __init__(self, host: str, model: str = DEFAULT_EMBED_MODEL, timeout: int = 120, batch: int = 32):
        self.host, self.model, self.timeout, self.batch = host.rstrip("/"), model, timeout, batch

    def _post(self, path: str, body: dict) -> dict:
        req = urllib.request.Request(self.host + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def digest(self) -> str:
        with urllib.request.urlopen(self.host + "/api/tags", timeout=10) as resp:
            for m in json.loads(resp.read())["models"]:
                if m["name"] in (self.model, f"{self.model}:latest") or m["model"] == self.model:
                    return m["digest"]
        raise ValueError(f"embedding model {self.model!r} is not pulled; run: ollama pull {self.model}")

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for i in range(0, len(texts), self.batch):
            out.extend(self._post("/api/embed", {"model": self.model, "input": list(texts[i:i + self.batch]),
                                                 "truncate": True})["embeddings"])
        return out


class HashEmbedder:
    """Deterministic bag-of-words embedder for tests and dry runs (no server, no model)."""
    model = "test/hash-embedder"

    def __init__(self, dims: int = 256):
        self.dims = dims

    def digest(self) -> str:
        return f"hash-{self.dims}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            v = [0.0] * self.dims
            for word in text.lower().split():
                word = word.strip(".,;:()[]")
                if word and word not in ("search_document", "search_query"):
                    v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dims] += 1.0
            vectors.append(v)
        return vectors


def _unit(v: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm else list(v)


@dataclass
class GuidelineIndex:
    chunks: list[Chunk]
    vectors: list[list[float]]     # unit length
    meta: dict

    def search(self, query_vector: Sequence[float], k: int = DEFAULT_K) -> list[tuple[Chunk, float]]:
        q = _unit(query_vector)
        scored = [(sum(a * b for a, b in zip(q, v)), i) for i, v in enumerate(self.vectors)]
        scored.sort(key=lambda s: (-s[0], self.chunks[s[1]].chunk_id))    # ties broken by ID: deterministic
        return [(self.chunks[i], round(score, 6)) for score, i in scored[:k]]


def build_index(embedder: Embedder, path: Path = DEFAULT_INDEX, chunks: list[Chunk] | None = None) -> dict:
    """Embed every passage and write the index; returns its metadata. Replaces an existing index file."""
    chunks = load_chunks() if chunks is None else chunks
    vectors = [_unit(v) for v in embedder.embed([DOC_PREFIX + c.text for c in chunks])]
    if len(vectors) != len(chunks) or len({len(v) for v in vectors}) != 1:
        raise ValueError("embedder returned the wrong number or shape of vectors")
    meta = {"corpus_sha256": corpus_sha256(chunks), "embed_model": embedder.model,
            "embed_digest": embedder.digest(), "n_chunks": len(chunks), "dims": len(vectors[0])}
    meta["index_sha256"] = hashlib.sha256(json.dumps(
        {"meta": meta, "vectors": [[round(x, 6) for x in v] for v in vectors]}, sort_keys=True).encode()).hexdigest()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.execute("CREATE TABLE rag_meta (key VARCHAR PRIMARY KEY, value VARCHAR)")
        con.executemany("INSERT INTO rag_meta VALUES (?, ?)", [(k, json.dumps(v)) for k, v in meta.items()])
        con.execute("CREATE TABLE rag_chunks (chunk_id VARCHAR PRIMARY KEY, source VARCHAR, text VARCHAR, "
                    "embedding DOUBLE[])")
        con.executemany("INSERT INTO rag_chunks VALUES (?, ?, ?, ?)",
                        [(c.chunk_id, c.source, c.text, v) for c, v in zip(chunks, vectors)])
    finally:
        con.close()
    tmp.replace(path)
    return meta


def load_index(path: Path = DEFAULT_INDEX) -> GuidelineIndex:
    con = duckdb.connect(str(path), read_only=True)
    try:
        meta = {k: json.loads(v) for k, v in con.execute("SELECT key, value FROM rag_meta").fetchall()}
        rows = con.execute("SELECT chunk_id, source, text, embedding FROM rag_chunks ORDER BY chunk_id").fetchall()
    finally:
        con.close()
    return GuidelineIndex([Chunk(c, s, t) for c, s, t, _ in rows], [list(r[3]) for r in rows], meta)


def open_index(embedder: Embedder, path: Path = DEFAULT_INDEX) -> GuidelineIndex:
    """Load the index, building it first when it is missing or was made from another corpus or embedding model."""
    path = Path(path)
    if path.is_file():
        index = load_index(path)
        current = corpus_sha256(load_chunks())
        if (index.meta.get("corpus_sha256") == current and index.meta.get("embed_model") == embedder.model
                and index.meta.get("embed_digest") == embedder.digest()):
            return index
    build_index(embedder, path)
    return load_index(path)


def retrieve(index: GuidelineIndex, embedder: Embedder, records: dict[int, str],
             k: int = DEFAULT_K) -> dict[int, list[tuple[Chunk, float]]]:
    """Top-k passages per case. Record text is used only in memory as the query."""
    ids = list(records)
    vectors = embedder.embed([QUERY_PREFIX + records[h][:QUERY_CHARS] for h in ids])
    return {h: index.search(v, k) for h, v in zip(ids, vectors)}


def format_passages(hits: list[tuple[Chunk, float]]) -> str:
    return "\n\n".join(f"[{n}] ({c.source}) {c.text}" for n, (c, _) in enumerate(hits, 1))
