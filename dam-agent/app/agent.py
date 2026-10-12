"""Orchestrator: plan -> fetch facts (tools) -> build prompt -> LLM -> guardrails."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from .config import Settings, settings
from .context import build_messages
from .guardrails import SAFETY_FOOTER, check_numbers, needs_safety_footer
from .router import Plan, make_plan
from .schemas import ChatRequest, ChatResult, Source
from .tools import ToolContext, run_tool
from .tools.base import ToolResult


@dataclass
class Prepared:
    plan: Plan
    results: list[ToolResult] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    facts_text: str = ""
    sources: list[Source] = field(default_factory=list)
    ui_actions: list[dict[str, Any]] = field(default_factory=list)
    canned: Optional[str] = None
    stats: dict = field(default_factory=dict)


class DamAgent:
    def __init__(self, *, llm, backend, registry, rag, memory, settings: Settings = settings) -> None:
        self.llm, self.backend, self.registry, self.rag, self.memory, self.s = llm, backend, registry, rag, memory, settings
        self.ctx = ToolContext(backend=backend, registry=registry, rag=rag, llm=llm, settings=settings)

    # ---------- planning + context ----------
    async def _prepare(self, req: ChatRequest) -> Prepared:
        dams = await self.registry.all()
        sess = self.memory.get(req.session_id)
        latest = max((d["lastRecorded"]["date"] for d in dams if d.get("lastRecorded")), default=time.strftime("%Y-%m-%d"))
        plan = make_plan(req.message, dams, req.page_context, sess, latest)
        p = Prepared(plan=plan, ui_actions=self._ui_actions(plan, req))
        if plan.canned:
            p.canned = plan.canned
            return p
        p.results = list(await asyncio.gather(*[run_tool(self.ctx, n, a) for n, a in plan.calls]))
        built = build_messages(dams=dams, page=req.page_context, history=sess.turns, question=req.message, results=p.results, latest=latest, s=self.s)
        p.messages, p.facts_text, p.sources, p.stats = built.messages, built.facts_text, built.sources, built.stats
        return p

    @staticmethod
    def _ui_actions(plan: Plan, req: ChatRequest) -> list[dict[str, Any]]:
        acts: list[dict[str, Any]] = []
        if plan.dam_ids:
            acts.append({"type": "select_dam", "dam_id": plan.dam_ids[0]})
        if plan.intent in ("forecast", "performance") and plan.horizon:
            acts.append({"type": "set_horizon", "value": plan.horizon})
        if plan.as_of:
            acts.append({"type": "set_as_of", "value": plan.as_of})
        if plan.intent in ("forecast", "performance") and plan.dam_ids and req.page_context.page != "predictions":
            q = f"?dam={plan.dam_ids[0]}" + (f"&horizon={plan.horizon}" if plan.horizon else "") + (f"&asOf={plan.as_of}" if plan.as_of else "")
            acts.append({"type": "navigate", "to": f"/predictions{q}"})
        return acts

    def _facts_only(self, p: Prepared) -> str:
        return "The language model is offline, so here are the raw facts I found:\n" + p.facts_text

    def _finish(self, req: ChatRequest, p: Prepared, answer: str, warnings: list[str], t0: float) -> ChatResult:
        if needs_safety_footer(req.message):
            answer = f"{answer}\n\n{SAFETY_FOOTER}"
        dam_id = p.plan.dam_ids[0] if p.plan.dam_ids else None
        self.memory.add_turn(req.session_id, req.message, answer, dam_id, p.plan.horizon)
        used = [s for s, r in zip(p.sources, p.results) if r.ok] if p.results else []
        return ChatResult(
            answer=answer, intent=p.plan.intent, tools=[n for n, _ in p.plan.calls], sources=used,
            warnings=warnings, ui_actions=p.ui_actions, latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    # ---------- non-streaming ----------
    async def run(self, req: ChatRequest) -> ChatResult:
        t0 = time.perf_counter()
        p = await self._prepare(req)
        if p.canned:
            return self._finish(req, p, p.canned, [], t0)
        warnings: list[str] = []
        try:
            answer = (await self.llm.chat(p.messages)).strip()
            bad = check_numbers(answer, p.facts_text)
            if bad:
                retry = p.messages + [
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": f"Your answer used numbers that are not in FACTS: {', '.join(bad)}. Rewrite it using ONLY numbers copied from FACTS, no arithmetic."},
                ]
                answer = (await self.llm.chat(retry)).strip()
                bad = check_numbers(answer, p.facts_text)
                if bad:
                    warnings.append("unverified_numbers: " + ", ".join(bad))
        except (httpx.HTTPError, RuntimeError):
            answer, warnings = self._facts_only(p), ["llm_unavailable"]
        return self._finish(req, p, answer, warnings, t0)

    # ---------- streaming (SSE events) ----------
    async def run_stream(self, req: ChatRequest) -> AsyncIterator[dict]:
        t0 = time.perf_counter()
        p = await self._prepare(req)
        yield {"event": "meta", "data": {"intent": p.plan.intent, "tools": [n for n, _ in p.plan.calls], "ui_actions": p.ui_actions}}
        warnings: list[str] = []
        if p.canned:
            answer = p.canned
            yield {"event": "token", "data": {"t": answer}}
        else:
            parts: list[str] = []
            try:
                async for tok in self.llm.stream(p.messages):
                    parts.append(tok)
                    yield {"event": "token", "data": {"t": tok}}
                answer = "".join(parts).strip()
                bad = check_numbers(answer, p.facts_text)
                if bad:
                    warnings.append("unverified_numbers: " + ", ".join(bad))
            except (httpx.HTTPError, RuntimeError):
                answer, warnings = self._facts_only(p), ["llm_unavailable"]
                yield {"event": "token", "data": {"t": answer}}
        result = self._finish(req, p, answer, warnings, t0)
        footer = result.answer[len(answer):] if result.answer.startswith(answer) else ""
        yield {"event": "done", "data": {**result.model_dump(), "footer": footer.strip()}}
