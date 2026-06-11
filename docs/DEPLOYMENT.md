# Deployment runbook (Part 9.3)

This project can be deployed as a single Docker web service. The backend serves both API routes
and the built frontend SPA.

## Runtime model

- App process: `uvicorn backend.app.main:app`
- API + UI served from one service:
  - API: `/api/*`
  - Frontend: `/` (static build + SPA fallback)
- Persistent state on disk:
  - SQLite database
  - Chroma vector index
  - Uploaded receipt files
- Policy PDFs are bundled in the image under `/app/data/policies` and should remain read-only.

## Required env vars

- `OPENAI_API_KEY` (secret; required)

Recommended runtime path vars for hosted deploys:

- `SQLITE_PATH=/app/runtime/northwind.db`
- `CHROMA_PATH=/app/runtime/chroma`
- `UPLOADS_DIR=/app/runtime/uploads`
- `POLICIES_DIR=/app/data/policies`

Why this split:
- Persistent disk is mounted at `/app/runtime`.
- Keeping `POLICIES_DIR` in `/app/data/policies` avoids masking policy PDFs with an empty mounted volume.

## Render deployment

Use `render.yaml` at repo root.

### Steps

1. Create a new Render Blueprint/Web Service from this repo.
2. Confirm service uses Docker build with `Dockerfile`.
3. Attach persistent disk at `/app/runtime` (configured in `render.yaml`).
4. Set `OPENAI_API_KEY` in Render dashboard (secret env var).
5. Deploy and wait for health check on `/api/health`.

### Verify on live URL

1. `GET /api/health` returns status `ok`.
2. `GET /` loads the frontend.
3. Create a submission, upload one receipt, and confirm verdict appears.
4. Restart service and confirm prior submissions still load (persistence check).

Automated smoke check:

```bash
uv run python eval/verify_live_url.py --base-url https://your-app-url
```

This verifies: health, frontend root, employees list, submission creation, upload+verdict flow,
submission detail, override write/read path, and out-of-scope Q&A refusal.

## Railway deployment (manual)

Railway can use the same Dockerfile.

### Steps

1. Create new project from repo.
2. Ensure Dockerfile build is selected.
3. Add persistent volume mounted to `/app/runtime`.
4. Set env vars:
   - `OPENAI_API_KEY`
   - `SQLITE_PATH=/app/runtime/northwind.db`
   - `CHROMA_PATH=/app/runtime/chroma`
   - `UPLOADS_DIR=/app/runtime/uploads`
   - `POLICIES_DIR=/app/data/policies`
5. Deploy and verify `/api/health`.

## Local Docker parity check

Build:

```bash
docker build -t northwind-pre-review:part9 .
```

Run:

```bash
docker run --rm -d -p 8000:8000 --name northwind-part9-smoke northwind-pre-review:part9
```

Health:

```bash
curl http://127.0.0.1:8000/api/health
```
