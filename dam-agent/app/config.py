"""Central settings. Override anything with environment variables or a .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _s(name: str, default: str) -> str:
    return os.getenv(name, default)


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _b(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    llm_provider: str          # "ollama" | "fake" (fake = no model, for tests / UI work)
    ollama_url: str
    chat_model: str
    embed_model: str
    use_embeddings: bool       # false = keyword (BM25) retrieval only
    num_ctx: int               # context window sent to Ollama. 6144 is safe on a 6 GB GPU
    max_new_tokens: int
    temperature: float
    keep_alive: str
    facts_budget_tokens: int   # max tokens of retrieved facts per question
    history_budget_tokens: int
    max_history_turns: int
    backend_base_url: str      # your existing API (the one the frontend calls)
    use_mock: bool             # true = synthetic levels/forecasts, no backend needed
    http_timeout: float
    knowledge_dir: Path
    data_dir: Path
    index_dir: Path
    cors_origins: list[str]
    admin_token: str


def load_settings() -> Settings:
    return Settings(
        app_name=_s("APP_NAME", "Jaladrishti"),
        llm_provider=_s("LLM_PROVIDER", "ollama"),
        ollama_url=_s("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        chat_model=_s("CHAT_MODEL", "qwen2.5-coder:7b"),
        embed_model=_s("EMBED_MODEL", "nomic-embed-text"),
        use_embeddings=_b("USE_EMBEDDINGS", False),
        num_ctx=_i("NUM_CTX", 6144),
        max_new_tokens=_i("MAX_NEW_TOKENS", 450),
        temperature=_f("TEMPERATURE", 0.2),
        keep_alive=_s("KEEP_ALIVE", "30m"),
        facts_budget_tokens=_i("FACTS_BUDGET_TOKENS", 1800),
        history_budget_tokens=_i("HISTORY_BUDGET_TOKENS", 1000),
        max_history_turns=_i("MAX_HISTORY_TURNS", 6),
        backend_base_url=_s("BACKEND_BASE_URL", "http://localhost:8000").rstrip("/"),
        use_mock=_b("USE_MOCK", True),
        http_timeout=_f("HTTP_TIMEOUT", 30.0),
        knowledge_dir=Path(_s("KNOWLEDGE_DIR", str(ROOT / "knowledge"))),
        data_dir=Path(_s("DATA_DIR", str(ROOT / "data"))),
        index_dir=Path(_s("INDEX_DIR", str(ROOT / "data" / "index"))),
        cors_origins=[o.strip() for o in _s("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
        admin_token=_s("ADMIN_TOKEN", ""),
    )


settings = load_settings()
