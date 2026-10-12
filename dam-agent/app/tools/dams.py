from __future__ import annotations

from typing import Optional

from .base import ToolContext, ToolResult, fmt, not_found


def _fill_pct(level: float, lo: float, hi: float) -> float:
    return max(0.0, min(100.0, (level - lo) / (hi - lo) * 100)) if hi > lo else 0.0


async def list_dams(ctx: ToolContext) -> ToolResult:
    dams = await ctx.registry.all()
    lines = []
    for d in dams:
        lr = d.get("lastRecorded") or {}
        pct = _fill_pct(lr["level"], d["minLevel"], d["maxLevel"]) if lr else None
        lines.append(f"- {d['name']} (id: {d['id']}) — {d.get('district') or '?'}, {d.get('state') or '?'}; latest {fmt(lr.get('level'))} {d.get('unit', '')} on {lr.get('date', 'n/a')}" + (f" ({fmt(pct, 1)}% of active range)" if pct is not None else ""))
    return ToolResult("list_dams", "Dam registry", lines or ["- The registry is empty."], {"count": len(dams)})


async def get_dam_info(ctx: ToolContext, dam_id: Optional[str] = None) -> ToolResult:
    d = await ctx.registry.get(dam_id)
    if not d:
        return not_found("get_dam_info", dam_id)
    u = d.get("unit", "")
    rows = [
        ("Name", d["name"]), ("Reservoir", d.get("reservoir")), ("River", d.get("river")),
        ("Location", d.get("location")), ("District", d.get("district")), ("State", d.get("state")),
        ("Year built", d.get("yearBuilt")), ("Purpose", d.get("purpose")),
        ("Full reservoir level (FRL)", f"{fmt(d['maxLevel'])} {u}"), ("Minimum / dead-pool level", f"{fmt(d['minLevel'])} {u}"),
        ("Gross storage", f"{fmt(d.get('grossStorage'))} TMC" if d.get("grossStorage") is not None else None),
        ("Live storage capacity", f"{fmt(d.get('liveStorage'))} TMC" if d.get("liveStorage") is not None else None),
        ("Dead storage", f"{fmt(d.get('deadStorage'))} TMC" if d.get("deadStorage") is not None else None),
        ("Catchment area", f"{fmt(d.get('catchmentArea'))} km²" if d.get("catchmentArea") is not None else None),
        ("Nearby places", ", ".join(d.get("nearbyPlaces") or []) or None),
        ("Regions affected on overflow", ", ".join(d.get("affectedRegions") or []) or None),
    ]
    lines = [f"- {k}: {v}" for k, v in rows if v not in (None, "", "None")]
    missing = [k for k, v in rows if v in (None, "", "None")]
    if missing:
        lines.append(f"- Not listed in the registry: {', '.join(missing)}.")
    return ToolResult("get_dam_info", "Dam registry", lines, {"dam_id": d["id"]})


async def compare_dams(ctx: ToolContext, dam_ids: Optional[list[str]] = None, top: int = 10) -> ToolResult:
    dams = await ctx.registry.all()
    if dam_ids:
        dams = [d for d in dams if d["id"] in dam_ids]
    rows = []
    for d in dams:
        lr = d.get("lastRecorded")
        if lr:
            rows.append((_fill_pct(lr["level"], d["minLevel"], d["maxLevel"]), d, lr))
    rows.sort(key=lambda r: -r[0])
    lines = [f"- {i + 1}. {d['name']}: {fmt(p, 1)}% of active range ({fmt(lr['level'])} {d.get('unit', '')} on {lr['date']}; FRL {fmt(d['maxLevel'])})" for i, (p, d, lr) in enumerate(rows[:top])]
    return ToolResult("compare_dams", "Dam registry (latest recorded levels)", lines or ["- No data to compare."], {"n": len(rows)})
