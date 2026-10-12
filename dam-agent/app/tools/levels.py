from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .base import ToolContext, ToolResult, fmt, not_found


def _fill_pct(level: float, lo: float, hi: float) -> float:
    return max(0.0, min(100.0, (level - lo) / (hi - lo) * 100)) if hi > lo else 0.0


async def _resolve(ctx: ToolContext, dam_id: Optional[str], as_of: Optional[str]):
    dam = await ctx.registry.get(dam_id)
    if not dam:
        return None, None
    latest = dam["lastRecorded"]["date"]
    return dam, min(as_of or latest, latest)


async def get_latest_level(ctx: ToolContext, dam_id: Optional[str] = None, as_of: Optional[str] = None) -> ToolResult:
    dam, target = await _resolve(ctx, dam_id, as_of)
    if not dam:
        return not_found("get_latest_level", dam_id)
    start = (date.fromisoformat(target) - timedelta(days=14)).isoformat()
    pts = [p for p in await ctx.backend.levels(dam, start, target) if p["date"] <= target]
    if not pts:
        return ToolResult("get_latest_level", "Level observations", [f"- No observation for {dam['name']} on or before {target}."], ok=False)
    p = pts[-1]
    u, lo, hi = dam.get("unit", ""), dam["minLevel"], dam["maxLevel"]
    lines = [
        f"- Reservoir: {dam['name']} (id: {dam['id']})",
        f"- Level on {p['date']}: {fmt(p['level'])} {u} (observed)",
        f"- Active range: minimum {fmt(lo)} {u} to full reservoir level (FRL) {fmt(hi)} {u}; level is {fmt(_fill_pct(p['level'], lo, hi), 1)}% of the range",
        f"- Below FRL by {fmt(max(0.0, hi - p['level']))} {u}",
    ]
    if p["date"] != target:
        lines.append(f"- Note: no reading on {target}; this is the latest reading before it.")
    return ToolResult("get_latest_level", "Level observations", lines, {"dam_id": dam["id"], "date": p["date"], "level": p["level"]})


async def get_history_summary(ctx: ToolContext, dam_id: Optional[str] = None, as_of: Optional[str] = None, days: int = 90) -> ToolResult:
    dam, target = await _resolve(ctx, dam_id, as_of)
    if not dam:
        return not_found("get_history_summary", dam_id)
    days = max(7, min(int(days or 90), 365))
    start = (date.fromisoformat(target) - timedelta(days=days)).isoformat()
    pts = [p for p in await ctx.backend.levels(dam, start, target) if p["date"] <= target]
    if len(pts) < 2:
        return ToolResult("get_history_summary", "Level observations", [f"- Not enough observations for {dam['name']} in the last {days} days."], ok=False)
    u, span = dam.get("unit", ""), dam["maxLevel"] - dam["minLevel"]
    lv = [p["level"] for p in pts]
    hi_p, lo_p = max(pts, key=lambda p: p["level"]), min(pts, key=lambda p: p["level"])

    def change(n: int) -> Optional[float]:
        return pts[-1]["level"] - pts[-1 - n]["level"] if len(pts) > n else None

    c7, c30 = change(7), change(30)
    trend = "steady"
    if c7 is not None and abs(c7) > 0.002 * span:
        trend = "rising" if c7 > 0 else "falling"
    lines = [
        f"- Reservoir: {dam['name']}; window: {pts[0]['date']} to {pts[-1]['date']} ({len(pts)} readings)",
        f"- Start {fmt(lv[0])} {u}, end {fmt(lv[-1])} {u}, net change {fmt(lv[-1] - lv[0])} {u}",
        f"- Highest {fmt(hi_p['level'])} {u} on {hi_p['date']}; lowest {fmt(lo_p['level'])} {u} on {lo_p['date']}; average {fmt(sum(lv) / len(lv))} {u}",
    ]
    if c7 is not None:
        lines.append(f"- Change over the last 7 days: {fmt(c7)} {u} ({trend})")
    if c30 is not None:
        lines.append(f"- Change over the last 30 days: {fmt(c30)} {u}")
    return ToolResult("get_history_summary", "Level observations", lines, {"dam_id": dam["id"], "trend": trend})
