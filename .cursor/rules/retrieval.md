---
description: Retrieval, citation, and refusal rules — apply when working on RAG, judgment, or Q&A code
globs:
  - "backend/**/retrieval*.py"
  - "backend/**/judge*.py"
  - "backend/**/qa*.py"
  - "backend/**/rag*.py"
---

# Retrieval, citation, and honesty rules

These govern all code that retrieves policy text, judges line items, or answers policy questions.
The graders explicitly and deliberately test these behaviors.

## Retrieval
- Chunk policies by SECTION (e.g., TEP-002 §2.3). Preserve doc_id, section number, and any
  cross-reference IDs as chunk metadata so a citation resolves to a real clause.
- The policy library contains deliberate NOISE documents (data classification, vendor onboarding,
  business continuity). Retrieval must surface the correct travel/expense clause, not the noise.
- Always carry similarity scores forward; they feed confidence and the refusal threshold.

## Citation faithfulness (hard rule)
- Every citation must quote text VERBATIM from a retrieved chunk. Never paraphrase, summarize, or
  invent clause wording.
- A cited clause must genuinely SUPPORT the verdict or answer it is attached to.
- After generation, VERIFY each quoted clause actually appears in a retrieved chunk. If it does not,
  drop the citation and downgrade the verdict to flagged/low-confidence — do not assert it anyway.
- Store citations as structured data: doc_id, section, exact quoted_text.

## Honest uncertainty / refusal (hard rule)
- If retrieval similarity is below the configured threshold, or required trip context is missing, or
  the item is genuinely ambiguous: return LOW confidence and FLAG for a human. Do not force a verdict.
- For ad-hoc Q&A: if the question is out of scope of the policy library, or retrieval is too weak,
  REFUSE clearly ("I can't find this in the policy library") rather than fabricating an answer.
- A refusal or a low-confidence flag is always preferable to a confident wrong answer.

## Verdict policy (flag vs reject vs human)
- Clear pass with supporting clause -> compliant.
- Clear, unambiguous violation with strong retrieval + supporting clause -> rejected.
- Borderline amount, weak/conflicting retrieval, or missing trip context -> flagged for human.
- Final confidence combines extraction quality, retrieval similarity, and the model's self-report.

## Trip context
- Judgment MUST consider employee/trip context, not just receipt content. Examples: alcohol on solo
  travel is non-reimbursable; conference registration that includes meals blocks separate meal
  claims; client entertainment caps differ from solo-travel caps and need recorded attendees.
