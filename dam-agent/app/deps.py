from __future__ import annotations

from .agent import DamAgent
from .config import Settings, settings
from .data_access.backend_client import BackendClient, DamRegistry
from .llm import get_llm
from .memory import SessionStore
from .rag.store import KnowledgeIndex


async def ensure_index(rag: KnowledgeIndex, registry: DamRegistry, llm, s: Settings = settings, force: bool = False) -> dict:
    from .rag.ingest import dam_card_chunks, load_markdown_chunks

    if not force and rag.load():
        return {"chunks": rag.size, "rebuilt": False}
    chunks, skipped = load_markdown_chunks(s.knowledge_dir)
    chunks += dam_card_chunks(await registry.all())
    emb = None
    if s.use_embeddings and s.llm_provider != "fake":
        try:
            emb = []
            for i in range(0, len(chunks), 16):
                emb += await llm.embed([c.title + "\n" + c.text for c in chunks[i : i + 16]])
        except Exception:
            emb = None
    rag.build(chunks, emb)
    return {"chunks": rag.size, "rebuilt": True, "skipped_todo_lines": skipped, "embeddings": emb is not None}


def build_agent(s: Settings = settings) -> tuple[DamAgent, KnowledgeIndex, DamRegistry]:
    backend = BackendClient(s)
    registry = DamRegistry(backend, s)
    rag = KnowledgeIndex(s.index_dir)
    llm = get_llm(s)
    agent = DamAgent(llm=llm, backend=backend, registry=registry, rag=rag, memory=SessionStore(), settings=s)
    return agent, rag, registry
