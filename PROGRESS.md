# Progress log

Update this after every verified slice. Newest entry on top. This is the memory anchor for fresh
Cursor chats — start each new chat by referencing docs/AGENTS.md, docs/PLAN.md, and this file.

## Status summary
- Current part: Part 7 (frontend UI)
- Last green commit: (working tree, not committed)
- Live URL: (not deployed)
- Known issues / TODO: current policy corpus is incomplete (only 8 PDFs), so judgment is conservative/flag-heavy when similarity or citation support is weak.

## Decisions log
Record any decision that deviates from or refines docs/AGENTS.md, with a one-line reason.
- (example) 2026-06-10 — Chose top_k=5 for retrieval; higher k pulled in noise docs on short queries.

## Slice log
Format: date - part - what was done - how it was verified - commit/tag

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
- [ ] Part 7: Frontend UI
- [ ] Part 8: Evaluation harness
- [ ] Part 9: Deployment, README, polish

## Verification checklist before final submission
- [ ] All 6 capabilities work in the browser on the live URL
- [ ] Data persists across a server restart on the deployed host
- [ ] Citations spot-checked against the real policy PDFs
- [ ] Out-of-scope Q&A is refused
- [ ] Eval harness runs with one command and prints metrics
- [ ] README defends tradeoffs + reports cost + scaling to 10k/day
- [ ] Public repo, live URL, README, eval harness all present
