"""Guideline RAG for Model A: public guideline passages retrieved per case and added to the prompt.

Circularity: the passages come from the same guidelines the Z3 rules were written from (data/guidelines/SOURCES.md),
so A+RAG measures whether the model follows guideline text it is shown, not external clinical knowledge.
"""
from clinverify.rag.corpus import Chunk, corpus_sha256, load_chunks  # noqa: F401
from clinverify.rag.store import (  # noqa: F401
    DEFAULT_EMBED_MODEL, DEFAULT_INDEX, DEFAULT_K, GuidelineIndex, HashEmbedder, OllamaEmbedder, build_index,
    format_passages, load_index, open_index, retrieve,
)
