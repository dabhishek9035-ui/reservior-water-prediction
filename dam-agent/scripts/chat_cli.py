"""Talk to the agent in the terminal (no server needed):
    python scripts/chat_cli.py --page predictions --dam bhadra --horizon 7"""
import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.deps import build_agent, ensure_index  # noqa: E402
from app.schemas import ChatRequest, PageContext  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="predictions")
    ap.add_argument("--dam")
    ap.add_argument("--horizon", type=int)
    ap.add_argument("--as-of")
    a = ap.parse_args()
    agent, rag, registry = build_agent()
    await ensure_index(rag, registry, agent.llm)
    ctx = PageContext(page=a.page, dam_id=a.dam, horizon=a.horizon, as_of=a.as_of)
    print("Dam assistant. Ctrl+C to quit.\n")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        print("bot> ", end="", flush=True)
        async for ev in agent.run_stream(ChatRequest(session_id="cli", message=q, page_context=ctx)):
            if ev["event"] == "token":
                print(ev["data"]["t"], end="", flush=True)
            elif ev["event"] == "done":
                d = ev["data"]
                print(f"\n     [{d['intent']} | tools: {', '.join(d['tools']) or '-'} | {d['latency_ms']} ms]" + (f" ⚠ {d['warnings']}" if d["warnings"] else ""))
                if d.get("footer"):
                    print("     " + d["footer"])


asyncio.run(main())
