from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from ..config import Settings


@dataclass
class ToolContext:
    backend: Any
    registry: Any
    rag: Any
    llm: Any
    settings: Settings


@dataclass
class ToolResult:
    name: str
    label: str                      # human-readable source label shown to the user
    lines: list[str]                # compact facts (each a "- ..." line)
    data: dict = field(default_factory=dict)
    ok: bool = True
    detail: Optional[str] = None


def fmt(x: Optional[float], nd: int = 2) -> str:
    if x is None:
        return "n/a"
    s = f"{x:,.{nd}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def not_found(name: str, dam_id: Optional[str]) -> ToolResult:
    return ToolResult(name, "Dam registry", [f"- No dam found with id '{dam_id}'."], ok=False)


def iso(d: date) -> str:
    return d.isoformat()
