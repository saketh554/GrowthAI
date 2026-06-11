from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _join(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify deployed/live Northwind API + UI basics.")
    parser.add_argument("--base-url", required=True, help="Deployed base URL, e.g. https://app.onrender.com")
    parser.add_argument(
        "--sample-receipt",
        default="data/submissions/01_clean_denver/receipts/03_uber_to_hotel.pdf",
        help="Local receipt file path used for remote upload-flow smoke test.",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    sample_receipt = Path(args.sample_receipt)
    assert_true(sample_receipt.exists(), f"sample receipt not found: {sample_receipt}")

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        health = client.get(_join(base_url, "/api/health"))
        assert_true(health.status_code == 200, f"health failed: {health.status_code} {health.text}")
        health_json = health.json()
        assert_true(health_json.get("status") == "ok", f"unexpected health payload: {health_json}")

        root = client.get(_join(base_url, "/"))
        assert_true(root.status_code == 200, f"root failed: {root.status_code}")
        assert_true(
            "text/html" in root.headers.get("content-type", ""),
            f"root is not html: {root.headers.get('content-type')}",
        )

        employees = client.get(_join(base_url, "/api/employees"))
        assert_true(employees.status_code == 200, f"employees failed: {employees.status_code} {employees.text}")
        employee_rows = employees.json()
        assert_true(isinstance(employee_rows, list) and len(employee_rows) > 0, "no employees returned")
        employee_id = employee_rows[0]["id"]

        created_submission = client.post(
            _join(base_url, "/api/submissions"),
            json={
                "employee_id": employee_id,
                "trip_purpose": "Live URL verification trip",
                "trip_dates": "2025-06-10 to 2025-06-11",
            },
        )
        assert_true(
            created_submission.status_code == 200,
            f"submission create failed: {created_submission.status_code} {created_submission.text}",
        )
        submission_id = created_submission.json()["id"]

        with sample_receipt.open("rb") as handle:
            files = {"files": (sample_receipt.name, handle, "application/pdf")}
            upload = client.post(_join(base_url, f"/api/submissions/{submission_id}/receipts"), files=files)
        assert_true(upload.status_code == 200, f"upload failed: {upload.status_code} {upload.text}")
        uploaded_rows = upload.json()
        assert_true(isinstance(uploaded_rows, list) and len(uploaded_rows) == 1, "expected one uploaded line item")
        verdicts = uploaded_rows[0].get("verdicts", [])
        assert_true(len(verdicts) >= 1, "expected at least one verdict after upload")

        detail = client.get(_join(base_url, f"/api/submissions/{submission_id}"))
        assert_true(detail.status_code == 200, f"submission detail failed: {detail.status_code} {detail.text}")
        detail_json: dict[str, Any] = detail.json()
        assert_true(len(detail_json.get("line_items", [])) >= 1, "submission detail missing line items")

        first_verdict_id = detail_json["line_items"][0]["verdicts"][-1]["id"]
        override = client.post(
            _join(base_url, f"/api/verdicts/{first_verdict_id}/override"),
            json={"reviewer_comment": "live-url smoke override", "new_verdict": "flagged"},
        )
        assert_true(override.status_code == 200, f"override failed: {override.status_code} {override.text}")

        out_of_scope = client.post(
            _join(base_url, "/api/qa"),
            json={"question": "What is the weather in Seattle tomorrow?"},
        )
        assert_true(out_of_scope.status_code == 200, f"qa failed: {out_of_scope.status_code} {out_of_scope.text}")
        qa_json = out_of_scope.json()
        assert_true(qa_json.get("refused") is True, f"expected refusal for out-of-scope question: {qa_json}")

        print("Part 9.5 live URL verification passed.")
        print(f"Base URL: {base_url}")
        print(f"Submission ID: {submission_id}")
        print(f"Uploaded line item verdict: {verdicts[-1]['verdict']}")
        print(f"Out-of-scope QA refusal reason: {qa_json.get('refusal_reason')}")
        print("Checks: health, frontend root, employees, submission create, upload flow, detail, override, qa refusal.")


if __name__ == "__main__":
    main()
