"""Assemble the prompt inside a hard token budget (7B model, small context window)."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .config import Settings, settings
from .prompts import build_system
from .schemas import PageContext, Source
from .tools.base import ToolResult


def est_tokens(text: str) -> int:
    return math.ceil(len(text) / 3.4)


@dataclass
class Built:
    messages: list[dict]
    facts_text: str
    sources: list[Source]
    stats: dict


def build_messages(*, dams: list[dict], page: PageContext, history: list[dict], question: str, results: list[ToolResult], latest: str, s: Settings = settings) -> Built:
    system = build_system(dams, page, latest)
    budget_total = s.num_ctx - s.max_new_tokens - 250
    facts_budget = min(s.facts_budget_tokens, max(300, budget_total - est_tokens(system) - est_tokens(question) - 150))

    blocks, sources, used, truncated = [], [], 0, False
    for i, r in enumerate(results, 1):
        sid = f"S{i}"
        head = f"[{sid}] {r.label}"
        lines = [head]
        used += est_tokens(head)
        for ln in r.lines:
            t = est_tokens(ln)
            if used + t > facts_budget:
                truncated = True
                break
            lines.append(ln)
            used += t
        blocks.append("\n".join(lines))
        sources.append(Source(id=sid, label=r.label, detail=r.detail))
    facts_text = "\n\n".join(blocks) if blocks else "(none retrieved)"
    user = f"FACTS (use only these; cite as [S#]):\n{facts_text}\n\nQUESTION: {question}"

    hist: list[dict] = []
    hbudget = min(s.history_budget_tokens, max(0, budget_total - est_tokens(system) - est_tokens(user)))
    spent = 0
    for m in reversed(history[-2 * s.max_history_turns :]):
        t = est_tokens(m["content"])
        if spent + t > hbudget:
            break
        hist.insert(0, m)
        spent += t
    if hist and hist[0]["role"] == "assistant":
        hist = hist[1:]

    messages = [{"role": "system", "content": system}, *hist, {"role": "user", "content": user}]
    stats = {"system_tokens": est_tokens(system), "facts_tokens": used, "history_tokens": spent, "facts_truncated": truncated, "budget": budget_total}
    return Built(messages, facts_text, sources, stats)
