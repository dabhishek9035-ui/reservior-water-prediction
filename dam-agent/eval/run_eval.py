"""Routing eval (offline, instant):   python eval/run_eval.py
Full eval through the real model:     python eval/run_eval.py --full   (needs Ollama running)
Add questions to eval/golden.jsonl as you find failures - it is your regression suite."""
import argparse
import asyncio
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.deps import build_agent, ensure_index  # noqa: E402
from app.memory import Session  # noqa: E402
from app.router import make_plan  # noqa: E402
from app.schemas import ChatRequest, PageContext  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()
    agent, rag, registry = build_agent()
    await ensure_index(rag, registry, agent.llm)
    dams = await registry.all()
    latest = max(d["lastRecorded"]["date"] for d in dams)
    rows = [json.loads(ln) for ln in (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    ok_intent = ok_tool = 0
    for r in rows:
        p = make_plan(r["q"], dams, PageContext(dam_id=dams[0]["id"]) if r["intent"] not in ("greeting", "out_of_scope") else PageContext(), Session(), latest)
        i_ok = p.intent == r["intent"]
        t_ok = (r["tool"] is None and not p.calls) or any(n == r["tool"] for n, _ in p.calls)
        ok_intent += i_ok
        ok_tool += t_ok
        if not (i_ok and t_ok):
            print(f"FAIL  {r['q']!r}\n      expected {r['intent']}/{r['tool']}  got {p.intent}/{[n for n, _ in p.calls]}")
        if a.full and not p.canned:
            res = await agent.run(ChatRequest(message=r["q"], stream=False, session_id="eval", page_context=PageContext(dam_id=dams[0]["id"])))
            print(f"  → {res.answer[:160]!r} warnings={res.warnings} {res.latency_ms}ms")
    n = len(rows)
    print(f"\nintent {ok_intent}/{n}  tool {ok_tool}/{n}")
    sys.exit(0 if ok_intent == n and ok_tool == n else 1)


asyncio.run(main())
