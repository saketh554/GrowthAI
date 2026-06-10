from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    app = create_app()
    client = TestClient(app)

    health = client.get("/api/health")
    assert_true(health.status_code == 200, "health endpoint failed")

    employees = client.get("/api/employees")
    assert_true(employees.status_code == 200, "employees endpoint failed")
    employee_rows = employees.json()
    assert_true(len(employee_rows) >= 5, "expected at least seeded employees")
    employee_id = employee_rows[0]["id"]

    new_submission = client.post(
        "/api/submissions",
        json={
            "employee_id": employee_id,
            "trip_purpose": "Part 5 verifier trip context",
            "trip_dates": "2025-06-10 to 2025-06-11",
        },
    )
    assert_true(new_submission.status_code == 200, "submission creation failed")
    submission_id = new_submission.json()["id"]

    receipt_path = Path("./data/submissions/01_clean_denver/receipts/03_uber_to_hotel.pdf")
    assert_true(receipt_path.exists(), "sample receipt missing for upload flow")
    with receipt_path.open("rb") as handle:
        files = {"files": (receipt_path.name, handle, "application/pdf")}
        upload = client.post(f"/api/submissions/{submission_id}/receipts", files=files)
    assert_true(upload.status_code == 200, "receipt upload flow failed")
    uploaded_rows = upload.json()
    assert_true(len(uploaded_rows) == 1, "expected exactly one uploaded line item")
    line_verdicts = uploaded_rows[0]["verdicts"]
    assert_true(len(line_verdicts) == 1, "expected verdict creation for uploaded line item")
    verdict_id = line_verdicts[0]["id"]

    listing = client.get("/api/submissions", params={"employee_id": employee_id})
    assert_true(listing.status_code == 200, "submission listing failed")
    assert_true(any(row["id"] == submission_id for row in listing.json()), "submission missing from listing")

    detail = client.get(f"/api/submissions/{submission_id}")
    assert_true(detail.status_code == 200, "submission detail failed")
    detail_payload = detail.json()
    assert_true(len(detail_payload["line_items"]) == 1, "detail missing line item")

    override = client.post(
        f"/api/verdicts/{verdict_id}/override",
        json={"reviewer_comment": "manual review", "new_verdict": "flagged"},
    )
    assert_true(override.status_code == 200, "override endpoint failed")

    qa = client.post("/api/qa", json={"question": "What is the dinner cap?"})
    assert_true(qa.status_code == 200, "qa endpoint failed")
    qa_body = qa.json()
    assert_true("answer" in qa_body, "qa response missing answer")
    assert_true("refused" in qa_body, "qa response missing refused flag")

    print("Part 5 verification passed.")
    print(f"Submission created: {submission_id}")
    print(f"Uploaded line item verdict: {line_verdicts[0]['verdict']}")
    print(f"QA refused: {qa_body['refused']}")


if __name__ == "__main__":
    main()
