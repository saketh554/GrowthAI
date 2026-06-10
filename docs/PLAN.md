# Project plan checklist

This document is the execution checklist for the Northwind Expense Pre-Review System.
Review `docs/AGENTS.md` for the full constitution before proceeding.

## Agreed constraints and decisions

- Backend: FastAPI (Python 3.11+), `uv` package manager.
- Frontend: React + Vite + Tailwind, single-page app; color-coded verdict cards.
- LLM: OpenAI gpt-4o (judging) + gpt-4o-mini (extraction); vision-capable. Swappable via config.
- Embeddings: text-embedding-3-small. Vector store: ChromaDB (persistent on disk).
- Relational DB: SQLite via SQLAlchemy (relational tables, NOT JSON blob). Survives restarts.
- Receipt formats: PDF, image (.jpg/.png), text (.txt). PyMuPDF for PDF text; vision for the rest.
- Schema-constrained LLM outputs everywhere. Verbatim-quoted citations. Honest refusal/low-conf.
- Local run via Docker; deploy to a public URL (Render/Railway) with a persistent disk.
- Git: one feature branch + commit-per-verified-slice; merge to main only when green.

## Git workflow

- `main` is always green and deployable.
- One branch per part (e.g., `feat/part-1-models`). PR per part, review the diff, merge, delete branch.
- Conventional commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- Tags: `v0.1-vertical-slice` (one receipt round-trips), `v1.0-mvp` (all 6 capabilities), `v1.1-deployed`.
- A commit must never contain code that has not been run/verified.

---

## Part 0: Scaffolding and guardrails

### Checklist
- [ ] Public GitHub repo; MIT license; `.gitignore` (.env, *.db, chroma/, node_modules).
- [ ] Init Python project with `uv`; pin Python 3.11+.
- [ ] Add `docs/` (AGENTS.md, PLAN.md, BRIEF.md) and `.cursor/rules/` (standards.md, retrieval.md).
- [ ] Add `PROGRESS.md`, `.env.example` (OPENAI_API_KEY).
- [ ] FastAPI skeleton with `/api/health`.
- [ ] Repo layout: `backend/`, `frontend/`, `eval/`, `data/`, `docs/`.

### Tests
- [ ] Server boots; `GET /api/health` returns expected JSON.
- [ ] `.gitignore` excludes secrets and DB/index files.

### Success criteria
- One command starts the backend locally; guardrail docs are in place and referenced.

---

## Part 1: Data models and persistence

### Checklist
- [ ] SQLAlchemy models: Employee, Submission, LineItem, Verdict, Override, QAQuery.
- [ ] Employee: id, name, grade, title, department, manager_id, home_base.
- [ ] Submission: id, employee_id, trip_purpose, trip_dates, status, created_at.
- [ ] LineItem: id, submission_id, receipt_filename, category, vendor, date, amount, currency, raw_extraction(JSON).
- [ ] Verdict: id, line_item_id, verdict, reasoning, cited_clauses(JSON: doc_id, section, quoted_text), confidence.
- [ ] Override: id, verdict_id, reviewer_comment, new_verdict, created_at (append-only).
- [ ] QAQuery: id, question, answer, refused(bool), cited_clauses(JSON), created_at.
- [ ] DB auto-creates on startup if missing; SQLite file on a persistent path.
- [ ] Seed script loads the 5 employees from employee_info.json on startup.

### Tests
- [ ] DB/schema can be created from a clean state.
- [ ] Seed inserts exactly the 5 provided employees with correct fields.
- [ ] Write a row, restart the process, confirm the row persists.

### Success criteria
- Relational state is persistent and survives restarts; employees are seeded automatically.

---

## Part 2: Policy ingestion and retrieval (RAG)

### Checklist
- [ ] Load all policy PDFs with PyMuPDF.
- [ ] Chunk by section (TEP-XXX §N); store doc_id + section + cross-references as metadata.
- [ ] Embed chunks with text-embedding-3-small; store in persistent Chroma.
- [ ] Build index once at startup (idempotent; skip if already built).
- [ ] `retrieve(query, k)` returns chunks + similarity scores + metadata.

### Tests
- [ ] Index builds from a clean state and persists to disk.
- [ ] Query "alcohol on solo travel" returns TEP-002 §6 / TEP-003, NOT the noise docs.
- [ ] Query "dinner cap" returns TEP-002 §2 with the correct dollar figure.
- [ ] Re-running startup does not re-embed an existing index.

### Success criteria
- Retrieval reliably surfaces the correct policy clause and ignores noise documents.

---

## Part 3: Receipt extraction (PDF + image + text)

### Checklist
- [ ] Pydantic `ExtractedReceipt` schema: vendor, date, amount, currency, category, meal_type?, line_details, attendees?.
- [ ] File-type router: .pdf -> PyMuPDF text, fall back to vision if no text layer; .jpg/.png -> vision; .txt -> read.
- [ ] Schema-constrained extraction via OpenAI structured outputs.
- [ ] Extraction-quality confidence signal (missing fields -> lower confidence).
- [ ] Graceful failure on unreadable/corrupt/foreign-currency files (mark for human, never crash).

### Tests
- [ ] All receipts in all 5 sample submissions extract without crashing.
- [ ] A synthetic .txt and .png receipt extract correctly.
- [ ] A corrupt/empty file is handled gracefully with low confidence.

### Success criteria
- Mixed-format receipts produce a validated structured record every time.

---

## Part 4: Judgment engine (core)

### Checklist
- [ ] Judge prompt inputs: extracted line item + employee/trip context + retrieved policy chunks.
- [ ] Pydantic `Verdict` schema: verdict, reasoning, cited_clauses(doc_id, section, exact quote), confidence.
- [ ] Post-check: each quoted clause must appear verbatim in a retrieved chunk; else downgrade/flag.
- [ ] Encode flag vs reject vs human rules (clear pass -> compliant; clear violation + strong retrieval -> rejected; borderline / weak retrieval / missing context -> flagged).
- [ ] Wire trip context into judgment (solo travel, client-vs-personal meals, conference-covered meals).
- [ ] Final confidence = extraction quality + retrieval similarity + model self-report.

### Tests
- [ ] Run all 5 submissions end-to-end; verdicts are sensible and well-explained.
- [ ] 03_dinner_over_cap -> rejected/flagged citing TEP-002 §2 (dinner $75).
- [ ] 04_alcohol_solo_travel -> rejected citing TEP-002 §6 / TEP-003.
- [ ] Spot-check: every quoted clause genuinely supports its verdict.

### Success criteria
- Verdicts are correct, explained, and backed by faithful verbatim citations.

---

## Part 5: Backend API

### Checklist
- [ ] GET /api/employees ; POST /api/employees.
- [ ] POST /api/submissions (employee + trip context).
- [ ] POST /api/submissions/{id}/receipts (multipart upload -> extract + judge + persist).
- [ ] GET /api/submissions (filter by employee, date, status).
- [ ] GET /api/submissions/{id} (line items, verdicts, overrides).
- [ ] POST /api/verdicts/{id}/override (append-only, with comment).
- [ ] POST /api/qa (retrieve -> cited answer OR refuse).
- [ ] Request/response validation models; clear HTTP error responses.

### Tests
- [ ] Each endpoint returns expected JSON via the OpenAPI/Swagger UI.
- [ ] Upload flow persists line items + verdicts.
- [ ] History filters return correct subsets.
- [ ] Override is recorded and retrievable; original verdict is preserved.

### Success criteria
- All six capabilities are exercisable through the API.

---

## Part 6: Policy Q&A with refusal

### Checklist
- [ ] Reuse retrieval for free-form questions.
- [ ] Similarity threshold below which the system refuses.
- [ ] Out-of-scope detection -> decline, never fabricate.
- [ ] Answers include verbatim-quoted citations (doc_id + section).
- [ ] Log every Q&A to QAQuery for auditability.

### Tests
- [ ] In-scope question returns a grounded, cited answer.
- [ ] Out-of-scope question (e.g., "what's the weather?") is refused.
- [ ] Weak-retrieval question is refused / marked low-confidence.

### Success criteria
- The system answers grounded policy questions and honestly declines the rest.

---

## Part 7: Frontend UI

### Checklist
- [ ] Employee picker (seeded list) + create-new-employee form.
- [ ] New-submission flow: select employee -> trip context -> upload receipts (mixed formats, drag-drop).
- [ ] Per-line-item review cards: category, verdict, reasoning, quoted clause(s), confidence.
- [ ] Color-code verdicts so flagged/rejected are visually distinct from compliant.
- [ ] Override button + comment box; show override history.
- [ ] History view with filters (employee/date/status); click into detail.
- [ ] Policy Q&A chat panel showing citations and a clear "declined" state.
- [ ] Loading and error states.

### Tests
- [ ] Click through all six capabilities in the browser end-to-end.
- [ ] Flagged/rejected items are visually distinct from compliant.
- [ ] Refresh / restart -> history and overrides remain.

### Success criteria
- A reviewer can do everything required from a normal browser.

---

## Part 8: Evaluation harness

### Checklist
- [ ] Define expected-outcomes JSON format (per item: verdict, expected policy doc, key clause; plus out-of-scope Q&A prompts).
- [ ] CLI: ingest JSON -> run pipeline -> compare -> print a metrics table.
- [ ] Metrics: verdict accuracy, retrieval quality (correct doc in top-k), citation correctness, refusal rate.
- [ ] Single command: `python eval/run.py --expected expected.json`.

### Tests
- [ ] Harness runs against a self-labeled version of the 5 samples and prints metrics.
- [ ] Dropping in a different expected JSON produces updated numbers.

### Success criteria
- Graders can drop in a held-out JSON and get the metrics that matter.

---

## Part 9: Deployment, README, and polish

### Checklist
- [ ] Dockerfile for local run; deploy config with a persistent disk (SQLite + Chroma).
- [ ] Deploy backend + frontend; obtain a live public URL.
- [ ] README: how to run locally + required API keys; architecture + diagram; tradeoff defenses
      (retrieval/chunking, model tiering, when vision is used, confidence handling, flag vs reject
      vs human); rough cost per submission + scaling to 10,000/day; what's next.
- [ ] Final code review: typed, readable, schema-constrained outputs, graceful failures.

### Tests
- [ ] Live URL exercises all six capabilities.
- [ ] Restart the deployed host -> data persists.
- [ ] README run-locally steps work from a clean clone.

### Success criteria
- Public repo, live URL, defended README, and eval harness — all four deliverables present.
