"""Retrieval layer: chunk report pages and rank them with BM25.

Retrieval decides *which* passages an LLM may see, so the full report is never
sent to a model: statement pages for structuring, a handful of passages for a
question, and only the insight brief for narrative insights. BM25 is lexical,
deterministic and runs offline; an embedding retriever can implement the same
``search`` signature later.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[a-z][a-z0-9&]+|\d+(?:\.\d+)?")
STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were will with
our we us their which also into than these those such been being not but can may per""".split())

CHUNK_CHARS = 900
CHUNK_OVERLAP = 150


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP]


@dataclass
class Chunk:
    id: str
    document_id: str
    document_name: str
    page: int
    text: str
    kind: str = "narrative"          # narrative | statement | notes
    tokens: Counter = field(default_factory=Counter, repr=False)
    length: int = 0


_RUNNING_HEADER = re.compile(r"^(\d{1,3}\s+)?.{0,60}(integrated annual report|annual report)\s*[\d\-]*(\s+\d{1,3})?$",
                             re.IGNORECASE)


def strip_running_headers(text: str) -> str:
    keep = [ln for ln in text.split("\n")
            if not (_RUNNING_HEADER.match(ln.strip()) or re.fullmatch(r"\d{1,3}(\s+\d{1,3})?", ln.strip()))]
    return "\n".join(keep)


def chunk_pages(document_id: str, document_name: str, pages: list[str], page_kinds: dict[int, str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page_no, text in enumerate(pages, start=1):
        text = strip_running_headers(text).strip()
        if len(text) < 40:
            continue
        start = 0
        n = 0
        while start < len(text):
            end = min(len(text), start + CHUNK_CHARS)
            if end < len(text):  # break at a line end when possible
                cut = text.rfind("\n", start + CHUNK_CHARS // 2, end)
                end = cut if cut > 0 else end
            body = text[start:end].strip()
            if body:
                n += 1
                chunks.append(Chunk(id=f"{document_id}:p{page_no}:{n}", document_id=document_id,
                                    document_name=document_name, page=page_no, text=body,
                                    kind=page_kinds.get(page_no, "narrative")))
            if end >= len(text):
                break
            start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


class BM25Index:
    def __init__(self, k1: float = 1.4, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.chunks: list[Chunk] = []
        self.df: Counter = Counter()
        self.avgdl = 0.0

    def add(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            toks = tokenize(c.text)
            c.tokens = Counter(toks)
            c.length = len(toks)
            self.df.update(set(toks))
            self.chunks.append(c)
        self.avgdl = sum(c.length for c in self.chunks) / max(len(self.chunks), 1)

    def idf(self, term: str) -> float:
        n = len(self.chunks)
        d = self.df.get(term, 0)
        return math.log(1 + (n - d + 0.5) / (d + 0.5))

    def search(self, query: str, k: int = 5, kinds: set[str] | None = None,
               document_id: str | None = None) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        if not q or not self.chunks:
            return []
        scored = []
        for c in self.chunks:
            if kinds and c.kind not in kinds:
                continue
            if document_id and c.document_id != document_id:
                continue
            s = 0.0
            for t in q:
                tf = c.tokens.get(t, 0)
                if tf:
                    s += self.idf(t) * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * c.length / self.avgdl))
            if s > 0:
                scored.append((c, s))
        scored.sort(key=lambda x: (-x[1], x[0].id))
        return scored[:k]

    def stats(self) -> dict:
        return {"chunks": len(self.chunks), "vocabulary": len(self.df), "avg_chunk_tokens": round(self.avgdl, 1),
                "retriever": "BM25 (lexical, offline)"}


def passage(c: Chunk, score: float | None = None, max_chars: int = 700) -> dict:
    flat = re.sub(r"\s*\n\s*", " ", c.text).strip()
    text = flat if len(flat) <= max_chars else flat[:max_chars].rsplit(" ", 1)[0] + " ..."
    out = {"chunk_id": c.id, "document": c.document_name, "page": c.page, "kind": c.kind, "text": text}
    if score is not None:
        out["score"] = round(score, 3)
    return out
