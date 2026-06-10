---
description: Global engineering standards for the Northwind expense pre-review system
alwaysApply: true
---

# Engineering standards (always apply)

Read `docs/AGENTS.md` and `docs/PLAN.md` before non-trivial work. Update `PROGRESS.md` after each
verified slice.

## Workflow
- Work in thin VERTICAL slices: get one path working end-to-end before broadening.
- For any non-trivial task, propose a short plan first, wait for approval, then edit.
- One sub-task = one focused diff. Do not sprawl edits across unrelated files.
- A change is not "done" until it has been RUN and verified. Never commit unrun code.

## Code quality
- Python 3.11+, full type hints, small readable functions. Readability is graded.
- Keep it simple. NEVER over-engineer. No speculative abstractions or unused config knobs.
- No emojis anywhere, including comments, logs, and the README.
- When debugging, find the ROOT CAUSE with evidence before changing code. Do not guess-and-check.

## LLM usage (hard rules)
- SCHEMA-CONSTRAINED OUTPUTS ONLY. Every structured LLM result uses a Pydantic model / structured
  outputs. Never parse free text with regex or string splitting.
- The receipt-reading model must be vision-capable; route PDFs without a text layer, images, and
  scanned docs through the vision path.
- Keep model choice and tier behind config so it can be swapped.

## Persistence (hard rule)
- All state lives in SQLite + ChromaDB on disk and must survive a server restart.
- In-memory storage of submissions, verdicts, overrides, or the index is NOT acceptable.
- Use relational tables (Employee, Submission, LineItem, Verdict, Override, QAQuery). Do NOT collapse
  the domain into a single JSON blob — history must be filterable by employee/date/status.

## Failure modes (never crash a request)
- Unreadable/corrupt file, missing amount/date, unsupported format, foreign currency, empty PDF text
  layer: catch it, mark the line item low-confidence / for-human, and return a clear message.

## Git
- Feature branch per part; conventional commits (feat/fix/test/docs/chore).
- Merge to main only when the slice runs green. Tag milestones.
