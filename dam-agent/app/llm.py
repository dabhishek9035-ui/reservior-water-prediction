"""LLM access. OllamaLLM talks to a local Ollama server; FakeLLM needs no model."""
from __future__ import annotations

import json
import re
from typing import AsyncIterator, Protocol

import httpx

from .config import Settings, settings


class LLM(Protocol):
    async def chat(self, messages: list[dict], **opts) -> str: ...
    def stream(self, messages: list[dict], **opts) -> AsyncIterator[str]: ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def health(self) -> bool: ...


class OllamaLLM:
    def __init__(self, s: Settings = settings) -> None:
        self.s = s
        self._timeout = httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)

    def _payload(self, messages: list[dict], stream: bool, **opts) -> dict:
        return {
            "model": self.s.chat_model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.s.keep_alive,
            "options": {
                "num_ctx": self.s.num_ctx,
                "temperature": opts.get("temperature", self.s.temperature),
                "num_predict": opts.get("max_new_tokens", self.s.max_new_tokens),
                "top_p": 0.9,
                "repeat_penalty": 1.05,
            },
        }

    async def chat(self, messages: list[dict], **opts) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self.s.ollama_url}/api/chat", json=self._payload(messages, False, **opts))
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def stream(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            async with c.stream("POST", f"{self.s.ollama_url}/api/chat", json=self._payload(messages, True, **opts)) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    obj = json.loads(line)
                    tok = obj.get("message", {}).get("content", "")
                    if tok:
                        yield tok
                    if obj.get("done"):
                        break

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(f"{self.s.ollama_url}/api/embed", json={"model": self.s.embed_model, "input": texts})
            r.raise_for_status()
            return r.json()["embeddings"]

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                return (await c.get(f"{self.s.ollama_url}/api/tags")).status_code == 200
        except httpx.HTTPError:
            return False


class FakeLLM:
    """Deterministic stand-in: restates the FACTS block. Useful for tests and frontend work."""

    async def chat(self, messages: list[dict], **opts) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        m = re.search(r"FACTS.*?\n(.*?)\n\nQUESTION:", user, re.S)
        lines = [ln[2:].strip() for ln in (m.group(1) if m else "").splitlines() if ln.startswith("- ")]
        tag = re.search(r"\[S\d+\]", user)
        if not lines:
            return "I don't have that information in the app's data."
        return " ".join(lines[:4]) + (f" {tag.group(0)}" if tag else "")

    async def stream(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        text = await self.chat(messages, **opts)
        for i in range(0, len(text), 24):
            yield text[i : i + 24]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("FakeLLM has no embeddings")

    async def health(self) -> bool:
        return True


def get_llm(s: Settings = settings) -> LLM:
    return FakeLLM() if s.llm_provider == "fake" else OllamaLLM(s)
