"""Turn knowledge/*.md and the dam registry into retrievable chunks.

Lines containing TODO are dropped, so unfinished placeholders are never served as facts."""
from __future__ import annotations

import re
from pathlib import Path

from .store import Chunk


def split_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(buf) + len(para) + 2 <= max_chars:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            parts.append(buf)
            buf = buf[-overlap:] + "\n\n" + para if overlap else para
        else:
            for i in range(0, len(para), max_chars - overlap):
                parts.append(para[i : i + max_chars])
            buf = ""
    if buf:
        parts.append(buf)
    return parts


def load_markdown_chunks(knowledge_dir: Path) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    skipped = 0
    for path in sorted(knowledge_dir.rglob("*.md")):
        rel = path.relative_to(knowledge_dir).as_posix()
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = []
        for ln in lines:
            if "TODO" in ln:
                skipped += 1
                continue
            kept.append(ln)
        doc_title, heading, buf = path.stem.replace("_", " "), "", []
        sections: list[tuple[str, str]] = []
        for ln in kept:
            if ln.startswith("# ") and doc_title == path.stem.replace("_", " "):
                doc_title = ln[2:].strip()
            elif ln.startswith("#"):
                if buf:
                    sections.append((heading, "\n".join(buf)))
                heading, buf = ln.lstrip("# ").strip(), []
            else:
                buf.append(ln)
        if buf:
            sections.append((heading, "\n".join(buf)))
        for h, body in sections:
            for j, piece in enumerate(split_text(body)):
                if len(piece.strip()) < 25:
                    continue
                title = f"{doc_title} › {h}" if h else doc_title
                chunks.append(Chunk(id=f"{rel}#{len(chunks)}", source=rel, title=title, text=piece.strip()))
    return chunks, skipped


def dam_card_chunks(dams: list[dict]) -> list[Chunk]:
    out = []
    for d in dams:
        bits = [
            f"{d['name']} ({d.get('reservoir') or d['name']}) is on the {d.get('river') or 'unknown'} river in {d.get('district') or 'unknown district'}, {d.get('state') or ''}.",
            f"Purpose: {d['purpose']}." if d.get("purpose") else "",
            f"Full reservoir level {d.get('maxLevel')} {d.get('unit', '')}; minimum level {d.get('minLevel')} {d.get('unit', '')}.",
            f"Places nearby: {', '.join(d['nearbyPlaces'])}." if d.get("nearbyPlaces") else "",
            f"Regions affected if it overflows: {', '.join(d['affectedRegions'])}." if d.get("affectedRegions") else "",
        ]
        out.append(Chunk(id=f"dam:{d['id']}", source="dams.json", title=f"Dam card › {d['name']}", text=" ".join(b for b in bits if b)))
    return out
