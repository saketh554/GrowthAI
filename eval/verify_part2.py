from __future__ import annotations

import shutil
from pathlib import Path

from backend.app.retrieval import RetrievalService
from backend.app.settings import Settings


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    base_settings = Settings()
    assert_true(bool(base_settings.openai_api_key), "OPENAI_API_KEY is required for Part 2 verification.")

    policies_path = Path(base_settings.policies_dir)
    assert_true(policies_path.exists(), f"Policies directory does not exist: {policies_path}")
    pdf_count = len(list(policies_path.glob("*.pdf")))
    assert_true(pdf_count > 0, "No policy PDFs found for retrieval verification.")

    verify_chroma = Path("./data/chroma_verify_part2")
    if verify_chroma.exists():
        shutil.rmtree(verify_chroma)
    verify_chroma.mkdir(parents=True, exist_ok=True)

    settings = Settings(chroma_path=str(verify_chroma))
    retrieval = RetrievalService(settings)

    first_build = retrieval.build_index_if_missing()
    first_count = retrieval._collection.count()
    assert_true(first_build["indexed_chunks"] > 0, "Index build did not add any chunks.")
    assert_true(first_build["indexed_docs"] > 0, "Index build did not detect any policy documents.")
    assert_true(first_count == first_build["indexed_chunks"], "Collection count mismatch after first build.")

    second_build = retrieval.build_index_if_missing()
    second_count = retrieval._collection.count()
    assert_true(second_count == first_count, "Index is not idempotent: chunk count changed on rebuild.")
    assert_true(
        second_build["indexed_chunks"] == second_count and second_build["indexed_docs"] == 0,
        "Expected idempotent rebuild to report existing chunks and zero newly indexed docs.",
    )

    for query in ["alcohol on solo travel", "dinner cap per person"]:
        results = retrieval.retrieve(query=query, k=3)
        assert_true(len(results) == 3, f"Expected 3 retrieval results for query: {query}")
        assert_true(any(result.doc_id.startswith("TEP-") for result in results), f"No TEP result for query: {query}")
        for result in results:
            assert_true(bool(result.text.strip()), f"Empty chunk text returned for query: {query}")
            assert_true(
                0.0 <= result.similarity <= 1.0,
                f"Similarity out of bounds for query {query}: {result.similarity}",
            )

    print("Part 2 verification passed.")
    print(f"Policy PDFs: {pdf_count}")
    print(f"Indexed chunks: {first_count}")
    print("Queries validated: alcohol on solo travel, dinner cap per person")


if __name__ == "__main__":
    main()
