# Northwind Expense Pre-Review

AI-assisted expense pre-review system for Northwind Logistics.

## Quick start

1. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.
2. Install dependencies and run backend:

```bash
uv sync
uv run uvicorn backend.app.main:app --reload
```

3. Verify health endpoint:

```bash
GET http://127.0.0.1:8000/api/health
```

## Repository layout

- `backend/` FastAPI API service
- `frontend/` React SPA (planned)
- `eval/` Evaluation harness (planned)
- `data/` Persistent local data (SQLite + Chroma)
- `docs/` Planning and project guidance
