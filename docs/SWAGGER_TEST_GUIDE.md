# Swagger UI Testing Guide

This guide walks you through testing every currently implemented backend endpoint from Swagger UI.

## Prerequisites

1. Ensure `.env` exists and contains a valid `OPENAI_API_KEY`.
2. Start the API from repository root:

```bash
uv run uvicorn backend.app.main:app --reload
```

3. Open Swagger UI:
   - [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Recommended test order

Use this order to avoid missing dependencies between endpoints:

1. `GET /api/health`
2. `GET /api/employees`
3. `POST /api/submissions`
4. `POST /api/submissions/{submission_id}/receipts`
5. `GET /api/submissions`
6. `GET /api/submissions/{submission_id}`
7. `POST /api/verdicts/{verdict_id}/override`
8. `POST /api/qa`
9. Optional diagnostics: `GET /api/retrieval/test`, `GET /api/extraction/test`, `GET /api/judgment/test`

---

## Endpoint details

### 1) `GET /api/health`

- **Purpose:** quick service liveness check.
- **Input:** none.
- **Expected 200 response:**

```json
{
  "status": "ok",
  "service": "northwind-backend"
}
```

### 2) `GET /api/employees`

- **Purpose:** list all seeded and manually created employees.
- **Input:** none.
- **Expected response:** array of employee objects with:
  - `id`, `name`, `grade`, `title`, `department`, `manager_id`, `home_base`.
- **What to verify:** at least the 5 seeded employees appear.

### 3) `POST /api/employees`

- **Purpose:** create a new employee for future submissions.
- **Request body example:**

```json
{
  "id": "NW-09999",
  "name": "Test Reviewer",
  "grade": 5,
  "title": "Ops Manager",
  "department": "Logistics Ops",
  "manager_id": "NW-03012",
  "home_base": "Irvine, CA"
}
```

- **Expected success:** returns created employee object.
- **Expected conflict:** `409` if `id` already exists.

### 4) `POST /api/submissions`

- **Purpose:** create an expense submission shell tied to an employee and trip context.
- **Request body example:**

```json
{
  "employee_id": "NW-04821",
  "trip_purpose": "Quarterly client review trip",
  "trip_dates": "2025-06-10 to 2025-06-12"
}
```

- **Expected success:** response with `id`, `status` (`new`), timestamps.
- **Expected error:** `404` if `employee_id` is unknown.

### 5) `POST /api/submissions/{submission_id}/receipts`

- **Purpose:** upload one or more receipt files and trigger full processing:
  - store file
  - extract structured fields
  - run policy judgment
  - persist line item + verdict
  - update submission status to `reviewed`
- **Input:** multipart form-data field named `files`.
- **How in Swagger UI:**
  1. Click `Try it out`.
  2. Set `submission_id` from step 4.
  3. Attach one or multiple PDF files from `data/submissions/.../receipts/`.
  4. Execute.
- **Expected response:** list of processed line items with nested `verdicts`.
- **What to verify per line item:**
  - extracted fields (`vendor`, `amount`, `date`, `currency`, `category`)
  - one verdict exists
  - verdict includes `reasoning`, `confidence`, and citations where available.

### 6) `GET /api/submissions`

- **Purpose:** browse submission history with optional filters.
- **Query params:**
  - `employee_id` (optional)
  - `status` (optional)
  - `start_date` (optional, ISO datetime format expected)
  - `end_date` (optional, ISO datetime format expected)
- **Expected success:** list of matching submissions sorted by newest first.
- **Expected error:** `400` for invalid date format.

### 7) `GET /api/submissions/{submission_id}`

- **Purpose:** fetch full submission detail for audit/review UI.
- **Includes:**
  - submission metadata
  - `line_items` with extraction payload
  - nested `verdicts`
  - all `overrides` tied to those verdicts
- **Expected error:** `404` if submission does not exist.

### 8) `POST /api/verdicts/{verdict_id}/override`

- **Purpose:** append a human override to a model verdict (audit trail).
- **Request body example:**

```json
{
  "reviewer_comment": "Manual correction after checking receipt notes",
  "new_verdict": "flagged"
}
```

- **Expected success:** created override record with timestamp.
- **Expected error:** `404` if verdict does not exist.

### 9) `POST /api/qa`

- **Purpose:** ask ad-hoc policy questions with grounded citations or refusal.
- **Request body example:**

```json
{
  "question": "What is the dinner cap per person?"
}
```

- **Expected response fields:**
  - `answer`
  - `refused` (boolean)
  - `cited_clauses` (list)
- **Behavior expectations:**
  - in-scope questions: grounded answer with verified citations when possible
  - weak/out-of-scope: refusal style answer with `refused=true`
- **Audit behavior:** each query is stored in `qa_queries`.

---

## Diagnostic endpoints (optional)

### `GET /api/retrieval/test`

- **Purpose:** inspect raw retrieval chunks for a query.
- **Use when:** you need to debug poor policy matching.

### `GET /api/extraction/test`

- **Purpose:** run extraction for a direct file path.
- **Use when:** checking field extraction quality for a specific receipt file.

### `GET /api/judgment/test`

- **Purpose:** run extraction + judgment on a file path with optional `trip_context`.
- **Use when:** debugging verdict outcomes and citation verification.

---

## End-to-end Swagger test script (manual)

1. Run `GET /api/employees` and copy one `employee_id`.
2. Create a submission via `POST /api/submissions`.
3. Upload a receipt via `POST /api/submissions/{id}/receipts`.
4. Open details via `GET /api/submissions/{id}` and copy one `verdict_id`.
5. Create an override via `POST /api/verdicts/{verdict_id}/override`.
6. Ask policy Q&A via `POST /api/qa`.
7. Re-open `GET /api/submissions/{id}` and confirm override appears in `overrides`.

If all seven steps succeed with expected payloads, Part 5 backend API flow is working correctly from Swagger UI.
