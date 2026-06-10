from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    app = create_app()
    client = TestClient(app)

    # In-scope policy question should be answerable or explicitly refused for low evidence.
    in_scope = client.post("/api/qa", json={"question": "What is the dinner cap per person?"})
    assert_true(in_scope.status_code == 200, "in-scope QA request failed")
    in_scope_body = in_scope.json()
    assert_true("answer" in in_scope_body, "in-scope response missing answer")
    assert_true("refused" in in_scope_body, "in-scope response missing refused flag")
    assert_true("refusal_reason" in in_scope_body, "in-scope response missing refusal_reason")
    if not in_scope_body["refused"]:
        assert_true(
            len(in_scope_body["cited_clauses"]) > 0,
            "in-scope non-refused answer must include citations",
        )

    # Out-of-scope question must be refused.
    out_of_scope = client.post("/api/qa", json={"question": "What is the weather in Seattle tomorrow?"})
    assert_true(out_of_scope.status_code == 200, "out-of-scope QA request failed")
    out_body = out_of_scope.json()
    assert_true(out_body["refused"] is True, "out-of-scope question should be refused")
    assert_true(out_body["refusal_reason"] == "out_of_scope", "unexpected refusal reason for out-of-scope")
    assert_true(len(out_body["cited_clauses"]) == 0, "out-of-scope refusal should not include citations")

    # Weak retrieval question should be refused.
    weak = client.post(
        "/api/qa",
        json={"question": "Under policy code TEP-9999, what is the lunar travel stipend?"},
    )
    assert_true(weak.status_code == 200, "weak-retrieval QA request failed")
    weak_body = weak.json()
    assert_true(weak_body["refused"] is True, "weak retrieval question should be refused")
    assert_true(
        weak_body["refusal_reason"]
        in {
            "low_similarity",
            "no_retrieval_results",
            "missing_grounded_citations",
            "out_of_scope",
            "insufficient_policy_support",
        },
        f"unexpected weak-retrieval refusal reason: {weak_body['refusal_reason']}",
    )
    assert_true(len(weak_body["cited_clauses"]) == 0, "weak-retrieval refusal should not include citations")

    print("Part 6 verification passed.")
    print(f"In-scope refused: {in_scope_body['refused']} ({in_scope_body['refusal_reason']})")
    print(f"Out-of-scope refused: {out_body['refused']} ({out_body['refusal_reason']})")
    print(f"Weak-retrieval refused: {weak_body['refused']} ({weak_body['refusal_reason']})")


if __name__ == "__main__":
    main()
