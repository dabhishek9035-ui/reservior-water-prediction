# Windows setup: venv + deps + models. Run from the dam-agent folder.
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
ollama pull qwen2.5-coder:7b
# optional: better plain Q&A / multilingual
# ollama pull qwen2.5:7b-instruct
# optional: embeddings (then set USE_EMBEDDINGS=true)
# ollama pull nomic-embed-text
.\.venv\Scripts\python scripts\ingest.py
Write-Host "Done. Start the API with: .\scripts\run_dev.ps1"
