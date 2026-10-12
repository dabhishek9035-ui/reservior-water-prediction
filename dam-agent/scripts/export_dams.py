"""Copy the dam list from your real backend into data/dams.json (used for mock mode + fallback).
    python scripts/export_dams.py http://localhost:8000"""
import json
import pathlib
import sys

import httpx

base = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
out = pathlib.Path(__file__).resolve().parent.parent / "data" / "dams.json"
data = httpx.get(f"{base}/api/dams", timeout=30).json()
out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(data)} dams to {out}")
