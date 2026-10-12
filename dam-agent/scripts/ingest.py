"""Rebuild the knowledge index:  python scripts/ingest.py"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.deps import build_agent, ensure_index  # noqa: E402


async def main() -> None:
    agent, rag, registry = build_agent()
    info = await ensure_index(rag, registry, agent.llm, force=True)
    print(info)
    if info.get("skipped_todo_lines"):
        print(f"Skipped {info['skipped_todo_lines']} TODO line(s) in knowledge/*.md - fill them in to teach the assistant more.")


asyncio.run(main())
