# Jaladrishti Architecture

This document describes the deployed runtime and the offline data/model
pipeline. The diagrams use Mermaid and render in GitHub, VS Code Markdown
preview, and other Mermaid-compatible documentation tools.

## System context and runtime flow

```mermaid
flowchart LR
    user([User])
    browser["Web browser"]

    subgraph frontend["Next.js 14 dashboard :3000"]
        pages["App routes\n/ · /dams · /predictions"]
        data["Data adapters\nsrc/data/api.ts · src/data/agent.ts"]
        ui["React UI\ncharts · maps · 3D scene · chat drawer"]
        mock["Mock/demo data\nNEXT_PUBLIC_USE_MOCK"]
        pages --> ui
        ui --> data
        data -. "when enabled" .-> mock
    end

    subgraph platform["Jaladrishti hydrology service :8000"]
        fastapi["FastAPI application\nbackend/main.py"]
        reservoir["ReservoirService\nsummaries · telemetry · time series"]
        forecast["ForecastService\nLSTM inference · baseline · simulation"]
        fastapi --> reservoir
        fastapi --> forecast
        static["Optional static serving\nfrontend/dist"]
        fastapi -. "if frontend/dist exists" .-> static
    end

    subgraph agent["Dam-agent service"]
        agentapi["FastAPI /chat + /health\nSSE streaming"]
        router["Deterministic intent/entity router"]
        tools["Domain tools\nlevels · forecast · dams · knowledge"]
        backendclient["BackendClient"]
        rag["RAG store\nknowledge/index"]
        memory["Session memory"]
        llm["Configured LLM provider"]
        agentapi --> router
        router --> tools
        tools --> backendclient
        tools --> rag
        router --> memory
        router --> llm
    end

    user --> browser
    browser --> frontend
    data -->|"REST /api/*"| fastapi
    data -->|"POST /chat\nServer-Sent Events"| agentapi
    backendclient -->|"REST /api/*"| fastapi
    agentapi -->|"streamed answer + sources + UI actions"| data
```

### Runtime responsibilities

- **Next.js dashboard** renders the reservoir register, historical charts,
  forecasts, scenario controls, and chat UI. `src/data/api.ts` validates and
  adapts backend responses with Zod.
- **FastAPI hydrology service** exposes health, statewide summary, reservoir
  telemetry, forecasts, scenario simulation, and evaluation metrics.
- **Dam-agent** provides domain-scoped chat. Its router decides which
  deterministic tools to call; the LLM writes an answer from fetched facts
  and retrieved knowledge. Responses are streamed as SSE events.
- **Filesystem artifacts** are the persistence layer: CSV observations,
  generated features, PyTorch checkpoints, scalers, manifests, evaluation
  results, and the agent's knowledge index.
- There is **no relational database or message broker** in the current
  architecture.

## Data and machine-learning pipeline

```mermaid
flowchart TD
    nwdp["NWDP / NWIC datastore\nreservoir observations"]
    openmeteo["Open-Meteo archive\npoint rainfall near dams"]
    fetchobs["fetch_daily_data.py"]
    fetchrain["fetch_rainfall.py"]
    obs[("data/imd_data/\n*_dam_ready.csv")]
    rain[("data/rainfall/\n*_dam_ready.csv")]

    build["build_features.py\nclean + join + engineer features"]
    features[("data/features/\n*_features.csv")]

    train["train/train_models.py\nchronological CV + candidate selection"]
    checkpoints[("train/models/\n*.pth · scalers · manifests")]
    evaluate["evaluate.py"]
    metrics[("evaluation/\nevaluation_results.csv")]

    runtime["FastAPI runtime"]
    service["ReservoirService"]
    inference["ForecastService"]
    baseline{"Artifacts available?"}
    lstm["PyTorch Delta-LSTM /\nIndependentHorizonLSTM\n1 · 7 · 14 · 30 days"]
    fallback["Discounted recent-trend /\npersistence baseline"]
    response["Forecast API response"]

    nwdp --> fetchobs --> obs
    openmeteo --> fetchrain --> rain
    obs --> build
    rain --> build
    build --> features
    features --> train
    train --> checkpoints
    features --> evaluate
    checkpoints --> evaluate
    evaluate --> metrics

    obs --> service
    features --> inference
    checkpoints --> inference
    inference --> baseline
    baseline -->|"yes"| lstm
    baseline -->|"no"| fallback
    lstm --> response
    fallback --> response
    service --> runtime
    response --> runtime
```

## Main API surface

| Method | Route | Component | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health` | FastAPI | Service health and monitored dam count |
| `GET` | `/api/summary` | ReservoirService | Statewide capacity, storage, inflow/outflow, and basin totals |
| `GET` | `/api/reservoirs` | ReservoirService | Current telemetry for monitored reservoirs |
| `GET` | `/api/reservoirs/{dam_id}` | ReservoirService | Metadata and historical time series |
| `GET` | `/api/reservoirs/{dam_id}/forecast` | ForecastService | 1-, 7-, 14-, and 30-day storage forecast |
| `POST` | `/api/reservoirs/{dam_id}/simulate` | ForecastService | Rainfall/outflow scenario trajectory |
| `GET` | `/api/evaluation` | ReservoirService | Model benchmark metrics |
| `POST` | `/chat` | Dam-agent | Domain-scoped streamed assistant response |

## Deployment notes

For local development, run the Next.js dashboard and the hydrology API as
separate processes. Start the dam-agent separately when chat is enabled. The
frontend uses `NEXT_PUBLIC_API_BASE_URL` for the hydrology API and
`NEXT_PUBLIC_AGENT_BASE_URL` for the agent service. If a production frontend
build is copied to `frontend/dist`, the FastAPI service can serve its static
assets as a single-process deployment.
