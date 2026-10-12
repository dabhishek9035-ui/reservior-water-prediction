from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PageContext(BaseModel):
    """What the user is looking at in the frontend. Sent with every message."""

    page: Optional[str] = None            # "home" | "dams" | "predictions"
    dam_id: Optional[str] = None
    horizon: Optional[int] = None         # 1 | 7 | 14 | 30
    as_of: Optional[str] = None           # YYYY-MM-DD
    window_days: Optional[int] = None
    show_predicted: Optional[bool] = None


class ChatRequest(BaseModel):
    session_id: str = Field(default="default", max_length=80)
    message: str = Field(min_length=1, max_length=2000)
    page_context: PageContext = Field(default_factory=PageContext)
    stream: bool = True


class Source(BaseModel):
    id: str
    label: str
    detail: Optional[str] = None


class ChatResult(BaseModel):
    answer: str
    intent: str
    tools: list[str]
    sources: list[Source]
    warnings: list[str]
    ui_actions: list[dict[str, Any]]
    latency_ms: int
