"""Talks to YOUR existing backend (the API the frontend uses), or serves mock data.

If your real endpoints differ, change ENDPOINTS and the two _norm_* helpers. Nothing else
in the agent knows about the wire format."""
from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx

from ..config import Settings, settings
from . import mock_data

ENDPOINTS = {
    "dams": "/api/reservoirs",
    "reservoir": "/api/reservoirs/{id}",
    "forecast": "/api/reservoirs/{id}/forecast",
}


def _first(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _int_keys(d: Optional[dict]) -> dict:
    return {int(k): v for k, v in (d or {}).items()}


def _norm_forecast(raw: dict, dam: dict, as_of: str, horizon: int) -> dict:
    # If the response has daily_trajectory_30d from backend/services/forecast_service.py
    if "daily_trajectory_30d" in raw or "forecast_horizons" in raw:
        horizons_data = raw.get("forecast_horizons", [])
        daily = raw.get("daily_trajectory_30d", [])
        curr_lvl = dam.get("lastRecorded", {}).get("level", 0.0)
        max_lvl = dam.get("maxLevel", curr_lvl or 1.0)
        min_lvl = dam.get("minLevel", max_lvl * 0.7)
        live_cap = max(0.001, float(dam.get("liveStorage") or dam.get("grossStorage") or 1.0))
        anchor_storage = float(raw.get("current_storage_tmc") or live_cap * 0.8)

        def tmc_to_ft(tmc: float) -> float:
            ratio = (tmc - anchor_storage) / live_cap
            return round(curr_lvl + ratio * (max_lvl - min_lvl), 2)

        preds = []
        for pt in daily:
            offset = pt.get("day_offset", 0)
            if 0 < offset <= horizon:
                tmc = pt.get("predicted_storage_tmc", anchor_storage)
                preds.append({
                    "date": pt.get("date"),
                    "level": tmc_to_ft(tmc),
                    "lower": None,
                    "upper": None,
                })
        h_pt = next((p for p in horizons_data if p.get("horizon_days") == horizon), None)
        if h_pt and preds:
            preds[-1]["lower"] = tmc_to_ft(h_pt.get("lower_bound_tmc", 0))
            preds[-1]["upper"] = tmc_to_ft(h_pt.get("upper_bound_tmc", 0))

        confidence_map = {1: 0.95, 7: 0.88, 14: 0.80, 30: 0.68}
        persistence_map = {h: curr_lvl for h in (1, 7, 14, 30)}
        source = raw.get("forecast_source", "trained_model")
        return {
            "dam_id": dam["id"],
            "as_of": as_of,
            "horizon": horizon,
            "source": source,
            "strategies": raw.get("strategies", {}),
            "predictions": preds,
            "confidence": confidence_map,
            "persistence": persistence_map,
            "actuals": [],
        }

    return {
        "dam_id": _first(raw, "dam_id", "damId", default=dam["id"]),
        "as_of": _first(raw, "as_of", "asOf", default=as_of),
        "horizon": int(_first(raw, "horizon", default=horizon)),
        "source": _first(raw, "source", default="trained_model"),
        "strategies": _int_keys(raw.get("strategies")),
        "predictions": [
            {"date": p["date"], "level": p["level"], "lower": p.get("lower"), "upper": p.get("upper")}
            for p in raw.get("predictions", [])
        ],
        "confidence": _int_keys(raw.get("confidence")),
        "persistence": _int_keys(raw.get("persistence")),
        "actuals": [{"date": p["date"], "level": p["level"]} for p in (raw.get("actuals") or [])],
    }


class BackendClient:
    def __init__(self, s: Settings = settings) -> None:
        self.s = s

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        async with httpx.AsyncClient(base_url=self.s.backend_base_url, timeout=self.s.http_timeout) as c:
            r = await c.get(path, params=params)
            r.raise_for_status()
            return r.json()

    async def dams(self) -> list[dict]:
        path = self.s.data_dir / "dams.json"
        local_dams = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if self.s.use_mock:
            return local_dams
        try:
            raw = await self._get(ENDPOINTS["dams"])
            if isinstance(raw, list) and raw:
                local_by_id = {d["id"]: d for d in local_dams}
                merged = []
                for item in raw:
                    d_id = item.get("id")
                    base_info = local_by_id.get(d_id, {})
                    cap = float(item.get("full_reservoir_level_ft") or base_info.get("maxLevel", 1800))
                    lvl = float(item.get("water_level_ft") or item.get("level") or base_info.get("lastRecorded", {}).get("level", cap * 0.8))
                    d = {
                        **base_info,
                        "id": d_id,
                        "name": item.get("short_name") or item.get("name") or base_info.get("name", d_id),
                        "reservoir": item.get("name") or base_info.get("reservoir", d_id),
                        "maxLevel": cap,
                        "lastRecorded": {
                            "date": item.get("latest_date") or base_info.get("lastRecorded", {}).get("date", "2026-09-27"),
                            "level": lvl,
                        },
                    }
                    merged.append(d)
                return merged
        except Exception:
            pass
        return local_dams

    async def levels(self, dam: dict, start: str, end: str) -> list[dict]:
        if not self.s.use_mock:
            try:
                raw = await self._get(ENDPOINTS["reservoir"].format(id=dam["id"]), {"history_days": 365})
                ts = raw.get("timeseries", [])
                if ts:
                    pts = []
                    for row in ts:
                        lvl = row.get("reservoir_level_ft")
                        if lvl is not None and float(lvl) > 0:
                            pts.append({"date": str(row["date"]), "level": float(lvl)})
                    if pts:
                        return sorted((p for p in pts if start <= p["date"] <= end), key=lambda p: p["date"])
            except Exception:
                pass
        return mock_data.levels(dam, start, end)

    async def forecast(self, dam: dict, as_of: str, horizon: int) -> dict:
        if not self.s.use_mock:
            try:
                raw = await self._get(ENDPOINTS["forecast"].format(id=dam["id"]))
                return _norm_forecast(raw, dam, as_of, horizon)
            except Exception:
                pass
        return mock_data.forecast(dam, as_of, horizon)



class DamRegistry:
    """Cached list of dams. Falls back to data/dams.json if the backend is down."""

    def __init__(self, backend: BackendClient, s: Settings = settings, ttl: float = 300.0) -> None:
        self.backend, self.s, self.ttl = backend, s, ttl
        self._dams: list[dict] = []
        self._at = 0.0
        self.source = "unknown"

    async def all(self) -> list[dict]:
        if self._dams and time.time() - self._at < self.ttl:
            return self._dams
        try:
            self._dams = await self.backend.dams()
            self.source = "mock" if self.s.use_mock else "backend"
        except Exception:
            path = self.s.data_dir / "dams.json"
            self._dams = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
            self.source = "file-fallback"
        self._at = time.time()
        return self._dams

    async def get(self, dam_id: Optional[str]) -> Optional[dict]:
        if not dam_id:
            return None
        return next((d for d in await self.all() if d["id"] == dam_id), None)
