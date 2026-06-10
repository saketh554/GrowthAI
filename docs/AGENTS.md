# Northwind Logistics — Expense Pre-Review System

## Business Requirements

Northwind Logistics is a mid-size logistics company. Their finance team manually reviews
employee expense submissions against a large library of company policies. We are building an
AI-assisted pre-review system that does the heavy lifting and explains its reasoning so a human
reviewer can trust or override it. A human always makes the final call.

A finance reviewer, from a normal browser, must be able to:

1. Start a new submission for an employee — pick an existing seeded employee or create a new one
   with identity + trip context.
2. Upload receipts in mixed formats (PDF, image .jpg/.png, plain text .txt) and have the system
   extract what is needed from each. Each receipt is one line item; the receipts ARE the claim.
3. See a per-line-item pre-review: category, verdict (compliant / flagged / rejected), reasoning,
   the policy clause(s) it relied on (quoted, not just referenced), and a confidence score.
   Flagged items must be visually distinct from compliant ones.
4. Override any verdict with a comment; the override must persist and be auditable.
5. Browse history of past submissions by employee, date, and status; click into any to see the
   original verdicts and applied overrides. State must persist across server restarts.
6. Ask ad-hoc questions about the policy library and receive cited, grounded answers — and have
   the system decline questions outside the policy library rather than fabricate.

## Limitations / MVP scope

- Single deployment, no real auth required for the MVP (a reviewer persona is assumed). The data
  model should still cleanly support multiple reviewers in future.
- Five employees are seeded on startup from the provided employee_info.json files. Reviewers do
  NOT upload JSON in the browser.
- Runs locally via Docker for development; also deployed to a public URL for grading.

## Technical Decisions

- Language: Python 3.11+.
- Backend: FastAPI + Uvicorn. Serves the API; can also serve the built frontend at `/`.
- Frontend: React + Vite + Tailwind (single-page app). Color-coded verdict cards.
- LLM: OpenAI gpt-4o for judging; gpt-4o-mini for cheap extraction. (Swappable via config.)
  The model MUST be vision-capable so the same path reads PDFs, images, and scanned receipts.
- Vision/OCR: gpt-4o vision is the primary path for images and scanned PDFs. PyMuPDF handles
  PDFs that have a real text layer. (Tesseract/Textract noted as a scale fallback.)
- Embeddings: OpenAI text-embedding-3-small.
- Vector store: ChromaDB, persistent on disk. (Migration path to pgvector/Postgres at scale.)
- Relational DB: SQLite via SQLAlchemy, file-backed so state survives restarts. RELATIONAL tables
  (Employee, Submission, LineItem, Verdict, Override, QAQuery) — NOT a single JSON blob, because
  the brief requires filtering history by employee/date/status and auditable overrides.
- PDF text extraction: PyMuPDF (fitz).
- Config/secrets: pydantic-settings + .env. OPENAI_API_KEY read from .env.
- Package manager: uv.
- Containerization: Docker for local; deploy to Render/Railway with a persistent disk.
- Eval harness: standalone Python CLI that ingests an expected-outcomes JSON and reports metrics.

## RAG / retrieval design

- Ingest all policy PDFs once at startup; build a persistent Chroma index (idempotent — skip if
  already built).
- Chunk by policy SECTION (e.g., TEP-002 §2.3), preserving doc_id and section number as metadata
  so citations resolve to a real clause. Keep cross-reference IDs in metadata.
- Some policy docs are deliberate NOISE (data classification, vendor onboarding, business
  continuity). Retrieval must surface the right travel/expense policy, not the noise.
- For each line item, retrieve top-k relevant chunks (with similarity scores) and pass them to the
  judgment step. The same retrieval powers the ad-hoc policy Q&A.

## Coding standards

1. Use latest stable versions of libraries and idiomatic approaches.
2. Keep it simple. NEVER over-engineer. ALWAYS simplify. No unnecessary defensive programming and
   no extra features beyond the requirements — but DO handle the real failure modes below.
3. Be concise. No emojis ever. README explains the WHY behind tradeoffs, not a feature list.
4. When hitting issues, identify the root cause before trying a fix. Do not guess. Prove with
   evidence, then fix the root cause.
5. SCHEMA-CONSTRAINED OUTPUTS ONLY. Every LLM call that produces structured data must use a
   Pydantic schema / structured outputs. Never parse free text with regex or string splitting.
6. CITATION FAITHFULNESS. Any policy citation must quote VERBATIM from a retrieved chunk. Never
   paraphrase, summarize, or invent clause text. If no retrieved clause supports a conclusion, do
   not assert it — flag for a human instead.
7. HONEST UNCERTAINTY. When retrieval similarity is low, context is missing, or a question is out
   of scope, return low confidence / refuse rather than guessing. A refusal beats a confident
   wrong answer.
8. PERSISTENCE, NOT IN-MEMORY. All state lives in SQLite + Chroma on disk and must survive a
   server restart. In-memory storage is not acceptable.
9. Typed code. Use type hints everywhere; readable functions kept small.
10. Graceful failure modes (never crash the request): unreadable/corrupt file, missing amount or
    date, unsupported format, foreign currency, empty PDF text layer. On failure, mark the line
    item low-confidence / for-human review with a clear message.

## Working documentation

All planning/execution docs live in `docs/`. Review `docs/PLAN.md` before proceeding. Update
`PROGRESS.md` after each verified slice. The condensed candidate brief is in `docs/BRIEF.md`.
