# Knowledge base

Everything the assistant knows beyond live data lives here as Markdown.

* Lines containing the word `TODO` are **skipped** at indexing time, so unfinished placeholders are never shown to users.
* Replace each `TODO` with a real fact, then run `python scripts/ingest.py` (or `POST /reindex`).
* Files starting with `_` and this README are ignored.
* One topic per `##` heading works best; keep sections under ~800 characters.
