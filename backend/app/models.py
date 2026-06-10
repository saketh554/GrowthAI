from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    manager_id: Mapped[str] = mapped_column(String(32), nullable=False)
    home_base: Mapped[str] = mapped_column(String(255), nullable=False)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="employee")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("employees.id"), nullable=False, index=True
    )
    trip_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    trip_dates: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="submissions")
    line_items: Mapped[list["LineItem"]] = relationship(back_populates="submission")


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("submissions.id"), nullable=False, index=True
    )
    receipt_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    raw_extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    submission: Mapped["Submission"] = relationship(back_populates="line_items")
    verdicts: Mapped[list["Verdict"]] = relationship(back_populates="line_item")


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("line_items.id"), nullable=False, index=True
    )
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    cited_clauses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    line_item: Mapped["LineItem"] = relationship(back_populates="verdicts")
    overrides: Mapped[list["Override"]] = relationship(back_populates="verdict")


class Override(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verdict_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("verdicts.id"), nullable=False, index=True
    )
    reviewer_comment: Mapped[str] = mapped_column(Text, nullable=False)
    new_verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    verdict: Mapped["Verdict"] = relationship(back_populates="overrides")


class QAQuery(Base):
    __tablename__ = "qa_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    refused: Mapped[bool] = mapped_column(nullable=False, default=False)
    cited_clauses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
