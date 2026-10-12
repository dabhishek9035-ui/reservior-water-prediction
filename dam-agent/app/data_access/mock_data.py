"""Synthetic levels and forecasts so the agent runs without your backend (USE_MOCK=true).
Everything produced here is labelled source="demo" so the assistant says so."""
from __future__ import annotations

import math
from datetime import date, timedelta


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _shape(dd: date) -> float:
    return 0.55 + 0.42 * math.cos(2 * math.pi * (dd.timetuple().tm_yday - 270) / 365)


def level_on(dam: dict, d: date) -> float:
    last_d = _d(dam["lastRecorded"]["date"])
    last_v = float(dam["lastRecorded"]["level"])
    lo, hi = float(dam["minLevel"]), float(dam["maxLevel"])
    span = hi - lo

    def noise(x: date) -> float:
        return span * 0.0015 * math.sin(x.toordinal() * 1.7)

    val = last_v + (_shape(d) - _shape(last_d)) * span * 0.9 + noise(d) - noise(last_d)
    return round(max(lo + 0.01 * span, min(hi, val)), 2)


def levels(dam: dict, start: str, end: str) -> list[dict]:
    s, e = _d(start), _d(end)
    last_d = _d(dam["lastRecorded"]["date"])
    e = min(e, last_d)
    out, cur = [], s
    while cur <= e:
        out.append({"date": cur.isoformat(), "level": level_on(dam, cur)})
        cur += timedelta(days=1)
    return out


def forecast(dam: dict, as_of: str, horizon: int) -> dict:
    a = _d(as_of)
    last_d = _d(dam["lastRecorded"]["date"])
    base = level_on(dam, a)
    span = float(dam["maxLevel"]) - float(dam["minLevel"])
    preds = []
    for i in range(1, horizon + 1):
        day = a + timedelta(days=i)
        lvl = base + (level_on(dam, day) - base) * 0.8
        w = span * 0.003 * math.sqrt(i)
        preds.append({"date": day.isoformat(), "level": round(lvl, 2), "lower": round(lvl - w, 2), "upper": round(lvl + w, 2)})
    actuals = []
    if a + timedelta(days=horizon) <= last_d:
        actuals = [{"date": (a + timedelta(days=i)).isoformat(), "level": level_on(dam, a + timedelta(days=i))} for i in range(1, horizon + 1)]
    return {
        "dam_id": dam["id"],
        "as_of": as_of,
        "horizon": horizon,
        "source": "demo",
        "strategies": {},
        "predictions": preds,
        "confidence": {1: 0.93, 7: 0.86, 14: 0.76, 30: 0.62},
        "persistence": {h: base for h in (1, 7, 14, 30)},
        "actuals": actuals,
    }
