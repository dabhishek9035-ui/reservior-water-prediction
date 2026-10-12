# Dam Agent (Jaladrishti assistant)

A local, grounded Q&A assistant for the dam-forecasting app. It answers questions about
**dams, reservoirs, water levels, forecasts, the model, data sources and regions** using a local
Qwen model through Ollama. Runs fully offline; no frontend wiring needed yet.

**How it stays accurate (the core idea):** a 7B model is bad at choosing tools and doing maths, so
*Python* decides what data to fetch (`app/router.py`), tools return compact, pre-computed facts
(`app/tools/`), and the model only *writes the answer* from those facts. Numbers in the reply are
checked against the facts (`app/guardrails.py`). If the model is down, users still get the raw facts.

```
question + page context ─► router (intent, dam, horizon, date)
                              │
              ┌───────────────┴────────────────┐
         live tools (your API)          knowledge base (knowledge/*.md, BM25 [+embeddings])
              └───────────────┬────────────────┘
                     FACTS block [S1] [S2]… (token-budgeted)
                              │
                     Qwen via Ollama ─► answer ─► number check ─► safety footer ─► SSE/JSON
```

## Quick start (Windows PowerShell)

```powershell
cd dam-agent
.\scripts\setup.ps1          # venv, deps, ollama pull qwen2.5-coder:7b, builds the index
.\scripts\run_dev.ps1        # http://localhost:8100  (docs at /docs)
```

No GPU/model yet? Set `LLM_PROVIDER=fake` in `.env` to exercise everything without a model.
Try it in the terminal: `python scripts/chat_cli.py --dam bhadra --horizon 7`

```powershell
curl -X POST http://localhost:8100/chat -H "Content-Type: application/json" `
  -d '{"message":"How full is Bhadra?","stream":false,"page_context":{"page":"predictions","dam_id":"bhadra"}}'
```

## Make it real (do these in order)

1. **Dams:** `python scripts/export_dams.py http://localhost:8000` copies your real dam list into `data/dams.json`
   (fields match the frontend `Dam` type). Then set `USE_MOCK=false` and `BACKEND_BASE_URL` in `.env`.
2. **Endpoints:** if your API paths differ, edit `ENDPOINTS` and `_norm_forecast` in `app/data_access/backend_client.py` (one file).
3. **Knowledge:** fill every `TODO` in `knowledge/*.md` (data sources, training data, accuracy, limitations, regions).
   `TODO` lines are never indexed, so the assistant says "I don't have that" instead of inventing. Then `python scripts/ingest.py`.
4. **Evaluate:** `python eval/run_eval.py` (routing, instant) and `python eval/run_eval.py --full` (real model). Add every failure to `eval/golden.jsonl`.
5. **Tests:** `pytest` (runs offline with the fake LLM).

## API

| Endpoint | Purpose |
|---|---|
| `POST /chat` | `{session_id, message, page_context, stream}`. `stream:true` → SSE events `meta`, `token`, `done`. |
| `GET /health` | model, Ollama reachability, mock/real data, index size |
| `DELETE /session/{id}` | clear a conversation |
| `POST /reindex` | rebuild the knowledge index (header `X-Admin-Token` if `ADMIN_TOKEN` is set) |

`page_context` = `{page, dam_id, horizon, as_of, window_days, show_predicted}` — the frontend sends what the user is looking at, so “what about 14 days?” just works.
The `done` event also returns `sources`, `warnings` (e.g. `unverified_numbers`, `llm_unavailable`) and `ui_actions` (`select_dam`, `set_horizon`, `set_as_of`, `navigate`) the UI can offer as buttons.

## Model notes (RTX 4050, 6 GB)

* `qwen2.5-coder:7b` (Q4) ≈ 4.7 GB. `NUM_CTX=6144` leaves room, but the 3D frontend also uses VRAM; if you see slowdowns lower `NUM_CTX` to 4096 or close other GPU apps.
* The Coder variant is tuned for code. For plain grounded Q&A (and Kannada/Hindi) `qwen2.5:7b-instruct` is usually better; it's a one-line change: `CHAT_MODEL=qwen2.5:7b-instruct`. Compare both with `eval/run_eval.py --full`.
* `scripts/Modelfile` bakes the context/temperature settings into a named Ollama model.

## Layout

```
app/        main.py (API) · agent.py · router.py · context.py · prompts.py · guardrails.py · llm.py · memory.py
app/tools/  dams · levels · forecast · knowledge   (+ TOOL_SCHEMAS for future native tool-calling)
app/rag/    BM25 (+ optional embeddings) index over knowledge/ and dam cards
knowledge/  Markdown the assistant may quote (fill the TODOs)
data/       dams.json (sample: Bhadra)      eval/  golden questions + runner
docs/       PLAN.md (design, phases, risks) · FRONTEND_INTEGRATION.md (for later)
```
