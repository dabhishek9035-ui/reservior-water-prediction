$python = if (Test-Path "..\venv\Scripts\python.exe") { "..\venv\Scripts\python.exe" } elseif (Test-Path "venv\Scripts\python.exe") { "venv\Scripts\python.exe" } else { "python" }
& $python -m uvicorn app.main:app --reload --port 8100 --host 127.0.0.1
