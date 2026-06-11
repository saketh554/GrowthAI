# Progress log

Update this after every verified slice. Newest entry on top. This is the memory anchor for fresh
Cursor chats — start each new chat by referencing docs/AGENTS.md, docs/PLAN.md, and this file.

## Status summary
- Current part: Part 9 (deployment, README, polish)
- Last green commit: (working tree, not committed)
- Live URL: (not deployed)
- Known issues / TODO: current policy corpus is incomplete (only 8 PDFs), so judgment is conservative/flag-heavy when similarity or citation support is weak.

## Decisions log
Record any decision that deviates from or refines docs/AGENTS.md, with a one-line reason.
- (example) 2026-06-10 — Chose top_k=5 for retrieval; higher k pulled in noise docs on short queries.
- 2026-06-10 — Execute Part 9 as gated sub-tasks (deployability -> docs -> live verification) to keep each slice independently verifiable.

## Part 9 execution plan (sub-tasks)
Work in strict order; do not start the next sub-task until the current one is verified.

- [ ] 9.1 Deployability baseline (local): add production-ready runtime wiring (backend startup command, static/frontend serving strategy, env-driven API base) and confirm local boot works from a clean shell.
  - Verify: backend health endpoint + frontend loads against production-style API base.
- [ ] 9.2 Containerization: add Dockerfile (and .dockerignore if missing) for backend+frontend artifact flow with persistent data paths for SQLite/Chroma.
  - Verify: `docker build` succeeds and container boots with `/api/health` reachable.
- [ ] 9.3 Deployment config + runbook: add platform config/docs for Render/Railway-style deployment with persistent disk mount requirements and env vars.
  - Verify: deployment instructions are executable end-to-end by following repo docs only.
- [ ] 9.4 README overhaul: document architecture (+ diagram), tradeoff rationale, confidence/flag-vs-reject policy, citation faithfulness constraints, eval harness usage, cost-per-submission estimate, and scaling to 10k/day.
  - Verify: README is sufficient for a clean-clone run and explicitly addresses brief deliverables.
- [ ] 9.5 Live URL validation: deploy and run browser/API smoke checks for all six capabilities on the public URL.
  - Verify: health, submission flow, mixed receipts, override persistence, history filters, and Q&A refusal on out-of-scope prompts.
- [ ] 9.6 Current repo polish: clean up technical debt and consistency gaps in existing code/docs (config hardcoding, naming consistency, stale docs, minor UX/API mismatches, and reliability papercuts).
  - Verify: targeted regressions pass; no new lint errors; updated docs match actual behavior.
- [ ] 9.7 Final polish + submission gate: run eval harness and verification checklist, then update `PROGRESS.md` status + final notes.
  - Verify: all checklist items below are checked or explicitly explained.

## Slice log
Format: date - part - what was done - how it was verified - commit/tag

- 2026-06-10 - Part 9.1 - established deployability baseline: made frontend API base env-driven (`VITE_API_BASE` with same-origin fallback), added backend static serving of built frontend (`/` + SPA fallback + `/assets`), and replaced hardcoded upload paths with `settings.uploads_dir`; expanded data-dir bootstrap for upload/sqlite parent dirs - verified with `npm run build` (frontend artifact generated) and FastAPI TestClient smoke checks (`GET /api/health` = 200, `GET /` serves HTML) - (not committed)
- 2026-06-10 - Part 8 - implemented `eval/run.py` evaluation harness (expected-outcomes JSON ingestion, line-item pipeline execution, QA execution, and metrics table for verdict accuracy/retrieval quality/citation correctness/refusal behavior) and added `eval/expected.sample.json` - verified with `uv run python eval/run.py --expected eval/expected.sample.json` (harness runs end-to-end and prints all required metrics) - (not committed)
- 2026-06-10 - Part 7 - scaffolded React+Vite+Tailwind frontend and implemented reviewer UI flows (employee selection, submission creation, mixed-file upload, per-line verdict cards with citations/confidence, override form/history, submission history/detail, and policy Q&A panel with decline state) - verified with `npm run build` and `uv run python eval/verify_part7.py` (frontend builds and produces dist artifact) - (not committed)
- 2026-06-10 - Part 6 - hardened policy QA refusal behavior with explicit out-of-scope refusal, low-similarity refusal, grounded-citation enforcement, and refusal reason field in API responses; added `eval/verify_part6.py` - verified with `uv run python eval/verify_part6.py` (in-scope grounded answer + out-of-scope refusal + weak-evidence refusal all pass) - (not committed)
- 2026-06-10 - Part 5 - implemented backend API endpoints for employees, submissions, receipt upload+extract+judge+persist flow, submission history/detail filters, verdict override, and policy QA logging; added typed API schemas and QA service - verified with `uv run python eval/verify_part5.py` (health, employees, submission creation, upload flow, listing/detail, override, and QA all pass) - (not committed)
- 2026-06-10 - Part 4 - added bulk evaluator `eval/verify_part4_bulk.py` and calibrated retrieval similarity mapping for Chroma distances to avoid over-flagging - verified with `uv run python eval/verify_part4_bulk.py` (34 receipts: 16 compliant, 5 rejected, 13 flagged; avg confidence 0.7292; non-flagged citation coverage 100%) - (not committed)
- 2026-06-10 - Part 4 - implemented judgment engine (`backend/app/judge.py`) with schema-constrained verdicts, retrieval+trip-context grounding, citation faithfulness verification (verbatim check and invalid citation removal), flag/reject/compliant logic, and confidence composition; wired test endpoint `/api/judgment/test` - verified with `uv run python eval/verify_part4.py` (structured verdicts + confidence + citation checks pass; conservative flagging observed when retrieval support is weak) - (not committed)
- 2026-06-10 - Part 3 - improved extraction normalization (vendor/date/currency/category/meal_type cleanup) and added bulk regression script `eval/verify_part3_bulk.py` - verified with `uv run python eval/verify_part3_bulk.py` (34/34 receipts high-confidence, 0 failures, 0 missing core fields) - (not committed)
- 2026-06-10 - Part 3 - implemented receipt extraction service with file router (`.pdf` text-first + vision fallback, `.jpg/.png` vision, `.txt` text), schema-constrained structured output (`ExtractedReceipt`), confidence scoring, and graceful failures; wired into app as `/api/extraction/test` - verified with `uv run python eval/verify_part3.py` (PDF + synthetic TXT extraction pass, missing-file graceful failure pass) - (not committed)
- 2026-06-10 - Part 2 - added repeatable verification script `eval/verify_part2.py` for clean-state index build, idempotency, and retrieval sanity checks - verified with `uv run python eval/verify_part2.py` (pass; 8 PDFs, 612 indexed chunks) - (not committed)
- 2026-06-10 - Part 2 - implemented policy PDF ingestion (PyMuPDF), section chunking with metadata/cross-refs, persistent Chroma index with OpenAI embeddings, and `retrieve(query,k)` service wired into app startup plus `/api/retrieval/test` endpoint - verified index build (612 chunks), idempotent rebuild behavior, and live retrieval queries for alcohol and dinner-cap prompts - (not committed)
- 2026-06-10 - Part 1 - added SQLAlchemy models (Employee/Submission/LineItem/Verdict/Override/QAQuery), SQLite bootstrap, and startup employee seeding from `submissions/*/employee_info.json` (idempotent) - verified schema creation, seed count=5, repeated startup remains 5, and persisted QA row survives restart - (not committed)
- 2026-06-10 - Part 0 - scaffolded Python project, created backend/frontend/eval/data layout, added FastAPI app and `/api/health`, aligned `.env.example` paths - verified with an ephemeral uvicorn run returning 200 + expected JSON from `/api/health` - (not committed)
- 2026-06-10 - Part 0 - repo scaffolded, docs + cursor rules added - server boots, /api/health 200 - (commit hash)
```
(add new entries above this line)
```

## Per-part completion (mirror of docs/PLAN.md)
- [x] Part 0: Scaffolding and guardrails
- [x] Part 1: Data models and persistence
- [x] Part 2: Policy ingestion and retrieval (RAG)
- [x] Part 3: Receipt extraction (PDF + image + text)
- [x] Part 4: Judgment engine
- [x] Part 5: Backend API
- [x] Part 6: Policy Q&A with refusal
- [x] Part 7: Frontend UI
- [x] Part 8: Evaluation harness
- [ ] Part 9: Deployment, README, polish

## Verification checklist before final submission
- [ ] All 6 capabilities work in the browser on the live URL
- [ ] Data persists across a server restart on the deployed host
- [ ] Citations spot-checked against the real policy PDFs
- [ ] Out-of-scope Q&A is refused
- [ ] Eval harness runs with one command and prints metrics
- [ ] README defends tradeoffs + reports cost + scaling to 10k/day
- [ ] Public repo, live URL, README, eval harness all present
