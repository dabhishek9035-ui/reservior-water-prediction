"""Small local retrieval index: BM25 (always) + optional embeddings (cosine), blended."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np

_TOK = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "is", "are", "in", "on", "and", "or", "for", "what", "how", "does", "do", "it", "this", "that", "with", "me", "tell", "about"}


def tokenize(text: str) -> list[str]:
    return [t for t in _TOK.findall(text.lower()) if t not in _STOP]


@dataclass
class Chunk:
    id: str
    source: str     # path relative to knowledge/ (or "dams.json")
    title: str
    text: str


class _BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.dl = [len(d) for d in docs]
        self.avg = sum(self.dl) / max(1, self.n)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, q: list[str]) -> list[float]:
        out = []
        for i in range(self.n):
            s = 0.0
            for t in q:
                f = self.tf[i].get(t)
                if not f:
                    continue
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avg or 1)))
            out.append(s)
        return out


class KnowledgeIndex:
    def __init__(self, index_dir: Path) -> None:
        self.dir = index_dir
        self.chunks: list[Chunk] = []
        self.emb: Optional[np.ndarray] = None
        self._bm25: Optional[_BM25] = None

    @property
    def size(self) -> int:
        return len(self.chunks)

    @property
    def has_embeddings(self) -> bool:
        return self.emb is not None

    def _rebuild_bm25(self) -> None:
        self._bm25 = _BM25([tokenize(c.title + " " + c.text) for c in self.chunks])

    def build(self, chunks: list[Chunk], embeddings: Optional[list[list[float]]] = None) -> None:
        self.chunks = chunks
        self.emb = None
        if embeddings:
            a = np.asarray(embeddings, dtype=np.float32)
            self.emb = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
        self._rebuild_bm25()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "chunks.json").write_text(json.dumps([asdict(c) for c in chunks], ensure_ascii=False), encoding="utf-8")
        emb_path = self.dir / "embeddings.npy"
        if self.emb is not None:
            np.save(emb_path, self.emb)
        elif emb_path.exists():
            emb_path.unlink()

    def load(self) -> bool:
        p = self.dir / "chunks.json"
        if not p.exists():
            return False
        self.chunks = [Chunk(**c) for c in json.loads(p.read_text(encoding="utf-8"))]
        ep = self.dir / "embeddings.npy"
        self.emb = np.load(ep) if ep.exists() else None
        if self.emb is not None and len(self.emb) != len(self.chunks):
            self.emb = None
        self._rebuild_bm25()
        return bool(self.chunks)

    def search(self, query: str, k: int = 3, qvec: Optional[list[float]] = None, prefix: Optional[str] = None, min_score: float = 0.05) -> list[tuple[Chunk, float]]:
        if not self.chunks or self._bm25 is None:
            return []
        bm = np.asarray(self._bm25.scores(tokenize(query)), dtype=np.float32)
        if bm.max() > 0:
            bm = bm / bm.max()
        score = bm
        if qvec is not None and self.emb is not None:
            q = np.asarray(qvec, dtype=np.float32)
            q = q / (np.linalg.norm(q) + 1e-9)
            score = 0.6 * bm + 0.4 * np.clip(self.emb @ q, 0, 1)
        order = np.argsort(-score)
        out: list[tuple[Chunk, float]] = []
        for i in order:
            if prefix and not self.chunks[i].source.startswith(prefix):
                continue
            if score[i] < min_score:
                break
            out.append((self.chunks[i], float(score[i])))
            if len(out) >= k:
                break
        return out
