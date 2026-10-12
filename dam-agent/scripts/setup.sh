#!/usr/bin/env bash
set -e
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
[ -f .env ] || cp .env.example .env
ollama pull qwen2.5-coder:7b
python scripts/ingest.py
echo "Done. Run: uvicorn app.main:app --reload --port 8100"
