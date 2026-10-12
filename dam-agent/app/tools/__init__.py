"""Tool registry. The router picks tools deterministically; TOOL_SCHEMAS is kept so you can
later let the LLM call them natively (Ollama /api/chat `tools=`) once you trust the model."""
from __future__ import annotations

import asyncio
from typing import Any

from .base import ToolContext, ToolResult
from .dams import compare_dams, get_dam_info, list_dams
from .forecast import get_forecast, get_model_performance
from .knowledge import get_region_info, search_knowledge
from .levels import get_history_summary, get_latest_level

TOOLS = {
    "list_dams": list_dams,
    "get_dam_info": get_dam_info,
    "compare_dams": compare_dams,
    "get_latest_level": get_latest_level,
    "get_history_summary": get_history_summary,
    "get_forecast": get_forecast,
    "get_model_performance": get_model_performance,
    "search_knowledge": search_knowledge,
    "get_region_info": get_region_info,
}

_DAM = {"dam_id": {"type": "string", "description": "Dam id from the registry"}}
_ASOF = {"as_of": {"type": "string", "description": "YYYY-MM-DD, defaults to latest"}}
_HZ = {"horizon": {"type": "integer", "enum": [1, 7, 14, 30]}}


def _fn(name: str, desc: str, props: dict, req: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": req or []}}}


TOOL_SCHEMAS = [
    _fn("list_dams", "List all dams with latest level.", {}),
    _fn("get_dam_info", "Static facts about one dam.", _DAM, ["dam_id"]),
    _fn("compare_dams", "Rank dams by how full they are.", {"dam_ids": {"type": "array", "items": {"type": "string"}}}),
    _fn("get_latest_level", "Observed level on a date.", {**_DAM, **_ASOF}, ["dam_id"]),
    _fn("get_history_summary", "Min/max/trend over a window.", {**_DAM, **_ASOF, "days": {"type": "integer"}}, ["dam_id"]),
    _fn("get_forecast", "Forecast for a horizon.", {**_DAM, **_ASOF, **_HZ}, ["dam_id"]),
    _fn("get_model_performance", "Backtest error vs persistence.", {**_DAM, **_HZ, "n_days": {"type": "integer"}}, ["dam_id"]),
    _fn("search_knowledge", "Search model card, data sources, glossary, app guide, regions.", {"query": {"type": "string"}}, ["query"]),
    _fn("get_region_info", "Region, nearby places, overflow-affected areas.", {**_DAM, "query": {"type": "string"}}),
]


async def run_tool(ctx: ToolContext, name: str, args: dict[str, Any], timeout: float = 25.0) -> ToolResult:
    fn = TOOLS.get(name)
    if fn is None:
        return ToolResult(name, "Tool", [f"- Unknown tool '{name}'."], ok=False)
    try:
        return await asyncio.wait_for(fn(ctx, **args), timeout)
    except asyncio.TimeoutError:
        return ToolResult(name, "Tool", [f"- The data source for '{name}' timed out."], ok=False)
    except Exception as e:  # never let a tool crash the chat
        return ToolResult(name, "Tool", [f"- The data source for '{name}' failed ({type(e).__name__})."], ok=False)
