from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EmployeeRead(BaseModel):
    id: str
    name: str
    grade: int
    title: str
    department: str
    manager_id: str
    home_base: str


class EmployeeCreate(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str
    grade: int
    title: str
    department: str
    manager_id: str
    home_base: str


class SubmissionCreate(BaseModel):
    employee_id: str
    trip_purpose: str
    trip_dates: str


class SubmissionRead(BaseModel):
    id: int
    employee_id: str
    trip_purpose: str
    trip_dates: str
    status: str
    created_at: datetime


class CitedClauseRead(BaseModel):
    doc_id: str
    section: str
    quoted_text: str


class VerdictRead(BaseModel):
    id: int
    line_item_id: int
    verdict: Literal["compliant", "flagged", "rejected"]
    reasoning: str
    cited_clauses: list[CitedClauseRead]
    confidence: float
    created_at: datetime


class OverrideRead(BaseModel):
    id: int
    verdict_id: int
    reviewer_comment: str
    new_verdict: Literal["compliant", "flagged", "rejected"]
    created_at: datetime


class LineItemRead(BaseModel):
    id: int
    submission_id: int
    receipt_filename: str
    category: str | None = None
    vendor: str | None = None
    date: str | None = None
    amount: float | None = None
    currency: str | None = None
    raw_extraction: dict | None = None
    verdicts: list[VerdictRead] = Field(default_factory=list)


class SubmissionDetail(BaseModel):
    submission: SubmissionRead
    line_items: list[LineItemRead] = Field(default_factory=list)
    overrides: list[OverrideRead] = Field(default_factory=list)


class OverrideCreate(BaseModel):
    reviewer_comment: str
    new_verdict: Literal["compliant", "flagged", "rejected"]


class QARequest(BaseModel):
    question: str


class QAResponse(BaseModel):
    answer: str
    refused: bool
    refusal_reason: str | None = None
    cited_clauses: list[CitedClauseRead] = Field(default_factory=list)

