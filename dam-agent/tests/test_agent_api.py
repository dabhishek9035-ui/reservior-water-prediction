import asyncio

from fastapi.testclient import TestClient

from app.main import app


def test_end_to_end_with_fake_llm():
    with TestClient(app) as c:
        h = c.get("/health").json()
        assert h["ok"] and h["index"]["chunks"] > 0

        r = c.post("/chat", json={"message": "How full is Bhadra?", "stream": False}).json()
        assert r["intent"] == "level" and "2,147.7" in r["answer"]
        assert r["sources"] and r["warnings"] == []

        r = c.post("/chat", json={"message": "Forecast for Bhadra in 7 days", "stream": False}).json()
        assert r["intent"] == "forecast" and any(a["type"] == "navigate" for a in r["ui_actions"])
        assert any("demo" in src["label"].lower() for src in r["sources"])

        r = c.post("/chat", json={"message": "Should we evacuate if Bhadra overflows?", "stream": False}).json()
        assert "not an official flood warning" in r["answer"]

        r = c.post("/chat", json={"message": "tell me a joke", "stream": False}).json()
        assert r["intent"] == "out_of_scope"

        r = c.post("/chat", json={"message": "what is FRL?", "stream": False}).json()
        assert "Full Reservoir Level" in r["answer"] or "highest level" in r["answer"]


def test_streaming_events():
    with TestClient(app) as c:
        with c.stream("POST", "/chat", json={"message": "How full is Bhadra?", "stream": True}) as resp:
            body = "".join(resp.iter_text())
        assert "event: meta" in body and "event: token" in body and "event: done" in body


def test_model_performance_tool():
    from app.deps import build_agent
    from app.tools import ToolContext, run_tool

    agent, rag, _ = build_agent()
    ctx = ToolContext(agent.backend, agent.registry, rag, agent.llm, agent.s)
    res = asyncio.run(run_tool(ctx, "get_model_performance", {"dam_id": "bhadra", "horizon": 7}))
    assert res.ok and any("persistence" in ln.lower() for ln in res.lines)
