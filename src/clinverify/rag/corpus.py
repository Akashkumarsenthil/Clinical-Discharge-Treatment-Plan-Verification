"""Guideline corpus for RAG: read data/guidelines/*.txt and cut it into passages.

The files are public guideline text scraped from journal pages (data/guidelines/SOURCES.md), so they carry page
navigation, author lists and reference entries. Cleaning keeps lines long enough to be prose, drops reference-list
lines and exact repeats, and keeps the header comments only for the source name. No MIMIC text is ever read here.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "data" / "guidelines"

CHUNKER_VERSION = "v1"
MIN_LINE_CHARS = 60          # shorter lines are navigation, headings or table fragments
MAX_CHUNK_CHARS = 1000       # about 250 tokens; three passages add under 1,000 tokens to the prompt
REFERENCE_LINE = re.compile(r"doi[:.]|\bPubMed\b|Google Scholar|Crossref|\bPMC\d+|https?://|et al\.,? \(?\d{4}", re.I)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str     # "<SOURCE>:<nnnn>", e.g. "SWE:0012"
    source: str       # catalog short name from the file name (SWE, WSES25, ILATAM, ACG26, KASID26)
    text: str


def source_name(path: Path) -> str:
    return path.stem.split("_", 1)[0]


def clean_lines(text: str) -> list[str]:
    seen, out = set(), []
    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue                                  # file header: citation, license, rule list
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < MIN_LINE_CHARS or REFERENCE_LINE.search(line) or line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def chunk_lines(lines: list[str], max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Greedy packing of whole lines into passages of at most max_chars; a longer line is split at sentence ends."""
    pieces = []
    for line in lines:
        if len(line) <= max_chars:
            pieces.append(line)
            continue
        part = ""
        for sentence in re.split(r"(?<=[.;:])\s+", line):
            if part and len(part) + 1 + len(sentence) > max_chars:
                pieces.append(part)
                part = ""
            part = f"{part} {sentence}".strip()
            while len(part) > max_chars:              # a single sentence longer than a passage
                pieces.append(part[:max_chars])
                part = part[max_chars:]
        if part:
            pieces.append(part)
    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + 1 + len(piece) > max_chars:
            chunks.append(current)
            current = ""
        current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def load_chunks(directory: Path = CORPUS_DIR) -> list[Chunk]:
    files = sorted(Path(directory).glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"no guideline .txt files in {directory}")
    chunks = []
    for path in files:
        src = source_name(path)
        for i, text in enumerate(chunk_lines(clean_lines(path.read_text(encoding="utf-8")))):
            chunks.append(Chunk(f"{src}:{i:04d}", src, text))
    return chunks


def corpus_sha256(chunks: list[Chunk]) -> str:
    """Hash of the exact passages (and chunker settings) that get embedded."""
    blob = json.dumps({"chunker": [CHUNKER_VERSION, MIN_LINE_CHARS, MAX_CHUNK_CHARS],
                       "chunks": [asdict(c) for c in chunks]}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()
