from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import __version__
from .config import settings
from .deps import build_agent, ensure_index
from .schemas import ChatRequest, ChatResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    agent, rag, registry = build_agent(settings)
    app.state.agent, app.state.rag, app.state.registry = agent, rag, registry
    app.state.index_info = await ensure_index(rag, registry, agent.llm, settings)
    yield


app = FastAPI(title="Dam Agent", version=__version__, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    llm_ok = await app.state.agent.llm.health()
    return {
        "ok": True, "version": __version__, "llm_provider": settings.llm_provider, "model": settings.chat_model,
        "llm_reachable": llm_ok, "mock_data": settings.use_mock, "dam_source": app.state.registry.source,
        "index": {"chunks": app.state.rag.size, "embeddings": app.state.rag.has_embeddings},
    }


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat", response_model=None)
async def chat(req: ChatRequest):
    agent = app.state.agent
    if not req.stream:
        return await agent.run(req)

    async def gen():
        async for ev in agent.run_stream(req):
            yield _sse(ev["event"], ev["data"])

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    app.state.agent.memory.clear(session_id)
    return {"cleared": session_id}


@app.post("/reindex")
async def reindex(x_admin_token: str = Header(default="")):
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="bad admin token")
    app.state.registry._dams = []   # drop the cache so dam cards are rebuilt from fresh data
    app.state.index_info = await ensure_index(app.state.rag, app.state.registry, app.state.agent.llm, settings, force=True)
    return app.state.index_info
