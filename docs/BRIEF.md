# Candidate Brief (condensed) — Northwind Logistics AI Engineer Case Study

This is a condensed reference of the original brief. The brief intentionally does NOT prescribe an
architecture — design choices are a large part of what is evaluated.

## Business problem
Northwind Logistics' finance team manually reviews employee expense submissions against a sprawling
policy library. Build an AI-assisted PRE-REVIEW system that ingests a submission and surfaces what a
reviewer needs to act on: what looks compliant, what looks like a violation and why, what is
ambiguous and needs a human. A human always makes the final call.

## What we are given
- `policies/` — ~30 policy PDFs (~100 pages). Most are travel & expense (TEP-001..TEP-014, which
  cross-reference each other like "TEP-002 §2.3"). A meaningful fraction are UNRELATED corporate
  policies (data classification, vendor onboarding, business continuity) included as realistic noise.
- `submissions/` — five sample expense submissions, each a folder with:
  - `employee_info.json` — identity, grade, manager, department, trip purpose and dates. SEED DATA:
    load all five employees on startup. Do NOT require reviewers to upload JSON in the browser.
  - `receipts/` — 4-8 receipts; each receipt is ONE line item. The receipts ARE the claim; there is
    no separate expense report.
- Grading will also use image (.jpg/.png) and plain-text (.txt) receipts. Do not assume PDFs only.

## Required capabilities (from a normal browser)
1. Start a submission — pick a seeded employee or create a new one with trip context.
2. Upload receipts in mixed formats; extract what is needed from each.
3. See a per-line-item pre-review: category, verdict (compliant/flagged/rejected), reasoning, the
   QUOTED policy clause(s), and confidence. Flagged items visually distinct.
4. Override any verdict with a comment; persisted and auditable.
5. Browse history by employee/date/status; click in to see verdicts + overrides. Persist across
   server restarts (in-memory is not acceptable).
6. Ask ad-hoc policy questions -> cited grounded answers; DECLINE out-of-scope questions.

## Sample submissions
A deliberate range: some clean, some real violations of different types, some require understanding
the employee's TRIP CONTEXT (not just the receipt) to reach the right verdict. Which is which is
revealed only after submission.

## Deliverables
1. Public GitHub repo.
2. Live deployed URL.
3. README: how to run locally + API keys; architecture + diagram; WHY behind tradeoffs (retrieval,
   chunking, model tier, when to use a vision model, confidence handling, flag-vs-reject-vs-human);
   rough cost per submission + scaling to 10,000 submissions/day; what's next.
4. Evaluation harness: a script run against a held-out set provided later. Accept a JSON of expected
   outcomes; return metrics (accuracy, retrieval quality, citation correctness, refusal rate on
   out-of-scope queries). Choosing the right metrics is part of the design.

## How it is evaluated
- Use the deployed system in the browser with the samples + their own test material.
- Read the code: pipeline structure, schema-constrained outputs vs free-text parsing, failure-mode
  handling, readability.
- Run the eval harness against a held-out set.
- Read the README for clear thinking about tradeoffs — not feature lists.

Strongest signal: an end-to-end system that demonstrably works + honest README reasoning.
Weakest signals: great backend with no UI; pretty UI on a broken backend; confident wrong answers
without acknowledging uncertainty; a feature-list README; no evaluation methodology.

## Called out explicitly
- No expected scoreboard — optimize for handling the messiness of real receipts and policies.
- Honest "I don't know" — refusing / low-confidence beats a confident wrong answer. They test this.
- Citation faithfulness — if the system says "TEP-X says Y," the quoted clause must support Y. Spot-checked.
- Persistence, not in-memory — yesterday's submission must be visible today after a restart.
- You may pick unusual tools — defend them in the README.

## Key policy facts to remember (from TEP-001 / TEP-002, verify against source)
- Approval thresholds (cumulative per submission): <= $1,000 manager; $1,000-$5,000 director; > $5,000 VP.
- Meal caps (per person, incl. tax + tip): breakfast $25, lunch $35, dinner $75. +25% in Tier 1 cities.
- Tips above 20% of pre-tax meal total are not reimbursable.
- Client entertainment caps: lunch $80, dinner $150/person; > $100/person needs prior VP approval;
  must record attendees + business purpose + external orgs.
- Alcohol on SOLO travel is never reimbursable (TEP-002 §6, TEP-003).
- Conference/training registration that includes meals -> no separate meal reimbursement (TEP-002 §5.1).
ALWAYS verify exact figures and section numbers against the actual policy PDFs before relying on them.
