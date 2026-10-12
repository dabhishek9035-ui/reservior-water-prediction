from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Optional

from .base import ToolContext, ToolResult, fmt, not_found

SNAP = (1, 7, 14, 30)


def _snap(h: Optional[int]) -> int:
    return min(SNAP, key=lambda x: abs(x - (h or 7)))


def _method(src: str, strategy: Optional[str]) -> tuple[str, Optional[str]]:
    if src == "historical_estimate":
        return "HISTORICAL ESTIMATE (a simple synthetic estimate for a past date, not a trained-model backtest)", "This is a historical estimate, not the trained model. Its uncertainty range is not calibrated."
    if src == "demo":
        return "DEMO forecast (illustrative data, not from the trained model)", "This is demo data. Do not present it as a real model forecast."
    names = {"persistence": "persistence (last level held)", "recent_trend": "recent-trend baseline", "delta_lstm": "Delta-LSTM model"}
    return f"trained model; strategy for this horizon: {names.get(strategy or '', strategy or 'saved best strategy')}", None


async def get_forecast(ctx: ToolContext, dam_id: Optional[str] = None, as_of: Optional[str] = None, horizon: Optional[int] = 7) -> ToolResult:
    dam = await ctx.registry.get(dam_id)
    if not dam:
        return not_found("get_forecast", dam_id)
    h = _snap(horizon)
    latest = dam["lastRecorded"]["date"]
    target_as_of = min(as_of or latest, latest)
    f = await ctx.backend.forecast(dam, target_as_of, h)
    if not f.get("predictions"):
        return ToolResult("get_forecast", "Forecast service", [f"- No forecast available for {dam['name']} as of {target_as_of} at {h} days."], ok=False)
    u, lo, hi = dam.get("unit", ""), dam["minLevel"], dam["maxLevel"]
    last = f["predictions"][-1]
    start = [p for p in await ctx.backend.levels(dam, (date.fromisoformat(target_as_of) - timedelta(days=7)).isoformat(), target_as_of) if p["date"] <= target_as_of]
    base = start[-1]["level"] if start else None
    method, caveat = _method(f.get("source", "trained_model"), (f.get("strategies") or {}).get(h))
    lines = [
        f"- Reservoir: {dam['name']}; forecast base date (as-of): {target_as_of}; horizon: {h} day(s); target date: {last['date']}",
        f"- Predicted level on {last['date']}: {fmt(last['level'])} {u}"
        + (f" (change vs as-of level {fmt(base)} {u}: {fmt(last['level'] - base)} {u})" if base is not None else ""),
        f"- Predicted level is {fmt(max(0.0, min(100.0, (last['level'] - lo) / (hi - lo) * 100)), 1)}% of the active range (FRL {fmt(hi)} {u})",
    ]
    if last.get("lower") is not None and last.get("upper") is not None and f.get("source") == "trained_model":
        lines.append(f"- Uncertainty range: {fmt(last['lower'])} to {fmt(last['upper'])} {u}")
    elif f.get("source") != "trained_model":
        lines.append("- Uncertainty range: not provided / not calibrated for this forecast type")
    conf = (f.get("confidence") or {}).get(h)
    if conf is not None:
        lines.append(f"- Model confidence for the {h}-day horizon: {fmt(conf * 100, 0)}%")
    pers = (f.get("persistence") or {}).get(h)
    if pers is not None:
        lines.append(f"- Persistence baseline (last observed level held steady): {fmt(pers)} {u}")
    lines.append(f"- Forecast method: {method}")
    if f.get("actuals"):
        act = f["actuals"][-1]
        err = abs(last["level"] - act["level"])
        line = f"- Observed actual on {act['date']}: {fmt(act['level'])} {u}; model absolute error {fmt(err)} {u}"
        if pers is not None:
            line += f"; persistence absolute error {fmt(abs(pers - act['level']))} {u}"
        lines.append(line)
    if caveat:
        lines.append(f"- IMPORTANT: {caveat}")
    label = {"trained_model": "Forecast service (trained model)", "historical_estimate": "Forecast service (historical estimate)", "demo": "Forecast service (demo data)"}.get(f.get("source", ""), "Forecast service")
    return ToolResult("get_forecast", label, lines, {"dam_id": dam["id"], "horizon": h, "as_of": target_as_of, "source": f.get("source")})


async def get_model_performance(ctx: ToolContext, dam_id: Optional[str] = None, horizon: Optional[int] = 7, n_days: int = 14) -> ToolResult:
    dam = await ctx.registry.get(dam_id)
    if not dam:
        return not_found("get_model_performance", dam_id)
    h, n = _snap(horizon), max(3, min(int(n_days or 14), 30))
    end = date.fromisoformat(dam["lastRecorded"]["date"]) - timedelta(days=h)
    sem = asyncio.Semaphore(4)

    async def one(d: date):
        async with sem:
            try:
                return await ctx.backend.forecast(dam, d.isoformat(), h)
            except Exception:
                return None

    fcs = await asyncio.gather(*[one(end - timedelta(days=i)) for i in range(n)])
    rows, sources = [], set()
    for f in fcs:
        if f and f.get("predictions") and f.get("actuals"):
            pers = (f.get("persistence") or {}).get(h)
            if pers is None:
                continue
            sources.add(f.get("source", "trained_model"))
            rows.append((f["predictions"][-1]["level"], f["actuals"][-1]["level"], pers))
    u = dam.get("unit", "")
    if not rows:
        return ToolResult("get_model_performance", "Backtest (stepped as-of dates)", [f"- No completed forecasts with observed outcomes for {dam['name']} at {h} days."], ok=False)
    mae = sum(abs(p - a) for p, a, _ in rows) / len(rows)
    pmae = sum(abs(q - a) for _, a, q in rows) / len(rows)
    rmse = (sum((p - a) ** 2 for p, a, _ in rows) / len(rows)) ** 0.5
    beats = sum(1 for p, a, q in rows if abs(p - a) < abs(q - a)) / len(rows) * 100
    lines = [
        f"- Reservoir: {dam['name']}; horizon: {h} day(s); backtest over the last {len(rows)} as-of dates with known outcomes",
        f"- Model mean absolute error: {fmt(mae)} {u}; RMSE: {fmt(rmse)} {u}",
        f"- Persistence baseline mean absolute error: {fmt(pmae)} {u}",
        f"- Model beat persistence on {fmt(beats, 0)}% of dates",
    ]
    if sources != {"trained_model"}:
        lines.append(f"- IMPORTANT: these forecasts come from source(s): {', '.join(sorted(sources))}; they are not real trained-model backtests.")
    return ToolResult("get_model_performance", "Backtest (stepped as-of dates)", lines, {"dam_id": dam["id"], "horizon": h})
