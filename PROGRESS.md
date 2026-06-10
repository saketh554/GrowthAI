# Progress log

Update this after every verified slice. Newest entry on top. This is the memory anchor for fresh
Cursor chats — start each new chat by referencing docs/AGENTS.md, docs/PLAN.md, and this file.

## Status summary
- Current part: Part 3 (receipt extraction)
- Last green commit: (working tree, not committed)
- Live URL: (not deployed)
- Known issues / TODO: current policy corpus is incomplete (only 8 PDFs), so retrieval cannot hit missing TEP docs from the brief.

## Decisions log
Record any decision that deviates from or refines docs/AGENTS.md, with a one-line reason.
- (example) 2026-06-10 — Chose top_k=5 for retrieval; higher k pulled in noise docs on short queries.

## Slice log
Format: date - part - what was done - how it was verified - commit/tag

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
- [ ] Part 3: Receipt extraction (PDF + image + text)
- [ ] Part 4: Judgment engine
- [ ] Part 5: Backend API
- [ ] Part 6: Policy Q&A with refusal
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
