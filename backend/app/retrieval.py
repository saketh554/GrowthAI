from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import fitz
from chromadb.api.models.Collection import Collection
from openai import OpenAI
from pydantic import BaseModel, Field

from backend.app.settings import Settings


SECTION_HEADER = re.compile(r"^\s*(\d+(?:\.\d+)*)[\)\.]?\s+(.+)$")
CROSS_REF = re.compile(r"\b([A-Z]{2,5}-\d{3}(?:\s*§\s*\d+(?:\.\d+)*)?)\b")


class PolicyChunk(BaseModel):
    chunk_id: str
    doc_id: str
    section: str
    text: str
    cross_references: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    section: str
    text: str
    similarity: float
    cross_references: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class PolicyDoc:
    doc_id: str
    raw_text: str


class OpenAIEmbeddingFunction:
    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=input)
        return [row.embedding for row in response.data]

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return f"openai:{self._model}"


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _read_pdf_text(path: Path) -> str:
    parts: list[str] = []
    doc = fitz.open(path)
    try:
        for page in doc:
            parts.append(page.get_text("text"))
    finally:
        doc.close()
    return "\n".join(parts)


def _doc_id_from_text(path: Path, text: str) -> str:
    file_stem = path.stem.upper()
    match = re.search(r"\b([A-Z]{2,5}-\d{3})\b", text)
    if match:
        return match.group(1)
    return file_stem


def _chunk_document(doc: PolicyDoc) -> list[PolicyChunk]:
    lines = [line.rstrip() for line in doc.raw_text.splitlines()]
    chunks: list[PolicyChunk] = []
    current_section = "intro"
    current_title = "Introduction"
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = _normalize_whitespace("\n".join(buffer))
        if not text:
            return
        section_label = f"{current_section} {current_title}".strip()
        refs = sorted(set(CROSS_REF.findall(text)))
        chunk_id = f"{doc.doc_id}:{current_section}:{len(chunks)}"
        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                doc_id=doc.doc_id,
                section=section_label,
                text=text,
                cross_references=refs,
            )
        )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        header_match = SECTION_HEADER.match(stripped)
        if header_match:
            flush()
            buffer = [stripped]
            current_section = header_match.group(1)
            current_title = _normalize_whitespace(header_match.group(2))
            continue
        buffer.append(stripped)

    flush()
    return chunks


def _load_policy_docs(policies_dir: str) -> list[PolicyDoc]:
    base = Path(policies_dir)
    if not base.exists():
        raise FileNotFoundError(f"Policies directory not found: {policies_dir}")

    docs: list[PolicyDoc] = []
    for pdf_path in sorted(base.glob("*.pdf")):
        text = _read_pdf_text(pdf_path)
        if not text.strip():
            continue
        docs.append(PolicyDoc(doc_id=_doc_id_from_text(pdf_path, text), raw_text=text))
    return docs


def _collect_chunks(policies_dir: str) -> list[PolicyChunk]:
    all_chunks: list[PolicyChunk] = []
    for doc in _load_policy_docs(policies_dir):
        all_chunks.extend(_chunk_document(doc))
    return all_chunks


def _collection(client: chromadb.ClientAPI, settings: Settings, openai_client: OpenAI) -> Collection:
    return client.get_or_create_collection(
        name="policy_chunks_v3",
        embedding_function=OpenAIEmbeddingFunction(openai_client, settings.embedding_model),
        metadata={"embedding_model": settings.embedding_model, "hnsw:space": "cosine"},
    )


class RetrievalService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._openai = OpenAI(api_key=settings.openai_api_key)
        self._client = chromadb.PersistentClient(path=settings.chroma_path)
        self._collection = _collection(self._client, settings, self._openai)

    def build_index_if_missing(self) -> dict[str, int]:
        existing = self._collection.count()
        if existing > 0:
            return {"indexed_chunks": existing, "indexed_docs": 0}

        chunks = _collect_chunks(self._settings.policies_dir)
        if not chunks:
            return {"indexed_chunks": 0, "indexed_docs": 0}

        by_doc = {chunk.doc_id for chunk in chunks}
        self._collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "doc_id": chunk.doc_id,
                    "section": chunk.section,
                    "cross_references": json.dumps(chunk.cross_references),
                }
                for chunk in chunks
            ],
        )
        return {"indexed_chunks": len(chunks), "indexed_docs": len(by_doc)}

    def retrieve(self, query: str, k: int | None = None) -> list[RetrievalResult]:
        top_k = k or self._settings.retrieval_top_k
        response = self._collection.query(query_texts=[query], n_results=top_k)
        ids = response.get("ids", [[]])[0]
        docs = response.get("documents", [[]])[0]
        metas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]

        results: list[RetrievalResult] = []
        for chunk_id, text, metadata, distance in zip(ids, docs, metas, distances, strict=False):
            similarity = 1.0 - float(distance)
            cross_refs = []
            if metadata and "cross_references" in metadata:
                raw_refs = metadata["cross_references"]
                if isinstance(raw_refs, str) and raw_refs:
                    cross_refs = json.loads(raw_refs)
            results.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    doc_id=str(metadata.get("doc_id", "")),
                    section=str(metadata.get("section", "")),
                    text=text,
                    similarity=similarity,
                    cross_references=cross_refs,
                )
            )
        return results
