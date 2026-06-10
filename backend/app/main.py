from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, select

from backend.app import models
from backend.app.bootstrap import init_persistence
from backend.app.db import session_scope
from backend.app.schemas import (
    EmployeeCreate,
    EmployeeRead,
    LineItemRead,
    OverrideCreate,
    OverrideRead,
    QARequest,
    QAResponse,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionRead,
    VerdictRead,
)
from backend.app.settings import Settings, ensure_data_dirs


def create_app() -> FastAPI:
    settings = Settings()
    ensure_data_dirs(settings)
    engine, session_factory, retrieval, extraction, judgment, qa = init_persistence(settings)

    app = FastAPI(title="Northwind Expense Pre-Review API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:4173",
            "http://localhost:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.retrieval = retrieval
    app.state.extraction = extraction
    app.state.judgment = judgment
    app.state.qa = qa

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "northwind-backend"}

    @app.get("/api/employees", response_model=list[EmployeeRead])
    def list_employees() -> list[EmployeeRead]:
        with session_scope(app.state.session_factory) as session:
            records = session.scalars(select(models.Employee).order_by(models.Employee.name)).all()
            return [
                EmployeeRead(
                    id=row.id,
                    name=row.name,
                    grade=row.grade,
                    title=row.title,
                    department=row.department,
                    manager_id=row.manager_id,
                    home_base=row.home_base,
                )
                for row in records
            ]

    @app.post("/api/employees", response_model=EmployeeRead)
    def create_employee(payload: EmployeeCreate) -> EmployeeRead:
        with session_scope(app.state.session_factory) as session:
            existing = session.get(models.Employee, payload.id)
            if existing is not None:
                raise HTTPException(status_code=409, detail="employee already exists")
            row = models.Employee(
                id=payload.id,
                name=payload.name,
                grade=payload.grade,
                title=payload.title,
                department=payload.department,
                manager_id=payload.manager_id,
                home_base=payload.home_base,
            )
            session.add(row)
            return EmployeeRead(
                id=row.id,
                name=row.name,
                grade=row.grade,
                title=row.title,
                department=row.department,
                manager_id=row.manager_id,
                home_base=row.home_base,
            )

    @app.post("/api/submissions", response_model=SubmissionRead)
    def create_submission(payload: SubmissionCreate) -> SubmissionRead:
        with session_scope(app.state.session_factory) as session:
            employee = session.get(models.Employee, payload.employee_id)
            if employee is None:
                raise HTTPException(status_code=404, detail="employee not found")
            row = models.Submission(
                employee_id=payload.employee_id,
                trip_purpose=payload.trip_purpose,
                trip_dates=payload.trip_dates,
                status="new",
            )
            session.add(row)
            session.flush()
            return SubmissionRead(
                id=row.id,
                employee_id=row.employee_id,
                trip_purpose=row.trip_purpose,
                trip_dates=row.trip_dates,
                status=row.status,
                created_at=row.created_at,
            )

    @app.post("/api/submissions/{submission_id}/receipts", response_model=list[LineItemRead])
    async def upload_receipts(
        submission_id: int,
        files: Annotated[list[UploadFile], File(...)],
    ) -> list[LineItemRead]:
        with session_scope(app.state.session_factory) as session:
            submission = session.get(models.Submission, submission_id)
            if submission is None:
                raise HTTPException(status_code=404, detail="submission not found")

            upload_dir = Path("./data/uploads") / str(submission_id)
            upload_dir.mkdir(parents=True, exist_ok=True)
            created: list[LineItemRead] = []

            for incoming in files:
                created.append(
                    _process_uploaded_file(
                        session=session,
                        submission=submission,
                        incoming=incoming,
                        upload_dir=upload_dir,
                        extraction_service=app.state.extraction,
                        judgment_service=app.state.judgment,
                    )
                )
            return created

    @app.post("/api/submissions/{submission_id}/receipt", response_model=LineItemRead)
    async def upload_receipt(submission_id: int, file: UploadFile = File(...)) -> LineItemRead:
        with session_scope(app.state.session_factory) as session:
            submission = session.get(models.Submission, submission_id)
            if submission is None:
                raise HTTPException(status_code=404, detail="submission not found")
            upload_dir = Path("./data/uploads") / str(submission_id)
            upload_dir.mkdir(parents=True, exist_ok=True)
            return _process_uploaded_file(
                session=session,
                submission=submission,
                incoming=file,
                upload_dir=upload_dir,
                extraction_service=app.state.extraction,
                judgment_service=app.state.judgment,
            )

    @app.get("/api/submissions", response_model=list[SubmissionRead])
    def list_submissions(
        employee_id: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[SubmissionRead]:
        with session_scope(app.state.session_factory) as session:
            query = select(models.Submission)
            filters = []
            if employee_id:
                filters.append(models.Submission.employee_id == employee_id)
            if status:
                filters.append(models.Submission.status == status)
            if start_date:
                try:
                    start_dt = datetime.fromisoformat(start_date)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="invalid start_date format") from exc
                filters.append(models.Submission.created_at >= start_dt)
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail="invalid end_date format") from exc
                filters.append(models.Submission.created_at <= end_dt)
            if filters:
                query = query.where(and_(*filters))
            rows = session.scalars(query.order_by(models.Submission.created_at.desc())).all()
            return [
                SubmissionRead(
                    id=row.id,
                    employee_id=row.employee_id,
                    trip_purpose=row.trip_purpose,
                    trip_dates=row.trip_dates,
                    status=row.status,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @app.get("/api/submissions/{submission_id}", response_model=SubmissionDetail)
    def get_submission(submission_id: int) -> SubmissionDetail:
        with session_scope(app.state.session_factory) as session:
            submission = session.get(models.Submission, submission_id)
            if submission is None:
                raise HTTPException(status_code=404, detail="submission not found")

            line_items = session.scalars(
                select(models.LineItem).where(models.LineItem.submission_id == submission_id)
            ).all()
            line_item_ids = [item.id for item in line_items]
            verdicts = (
                session.scalars(select(models.Verdict).where(models.Verdict.line_item_id.in_(line_item_ids))).all()
                if line_item_ids
                else []
            )
            verdicts_by_line: dict[int, list[models.Verdict]] = {}
            for verdict in verdicts:
                verdicts_by_line.setdefault(verdict.line_item_id, []).append(verdict)

            verdict_ids = [verdict.id for verdict in verdicts]
            overrides = (
                session.scalars(select(models.Override).where(models.Override.verdict_id.in_(verdict_ids))).all()
                if verdict_ids
                else []
            )

            return SubmissionDetail(
                submission=SubmissionRead(
                    id=submission.id,
                    employee_id=submission.employee_id,
                    trip_purpose=submission.trip_purpose,
                    trip_dates=submission.trip_dates,
                    status=submission.status,
                    created_at=submission.created_at,
                ),
                line_items=[
                    LineItemRead(
                        id=item.id,
                        submission_id=item.submission_id,
                        receipt_filename=item.receipt_filename,
                        category=item.category,
                        vendor=item.vendor,
                        date=item.date,
                        amount=item.amount,
                        currency=item.currency,
                        raw_extraction=item.raw_extraction,
                        verdicts=[
                            VerdictRead(
                                id=verdict.id,
                                line_item_id=verdict.line_item_id,
                                verdict=verdict.verdict,
                                reasoning=verdict.reasoning,
                                cited_clauses=verdict.cited_clauses,
                                confidence=verdict.confidence,
                                created_at=verdict.created_at,
                            )
                            for verdict in verdicts_by_line.get(item.id, [])
                        ],
                    )
                    for item in line_items
                ],
                overrides=[
                    OverrideRead(
                        id=item.id,
                        verdict_id=item.verdict_id,
                        reviewer_comment=item.reviewer_comment,
                        new_verdict=item.new_verdict,
                        created_at=item.created_at,
                    )
                    for item in overrides
                ],
            )

    @app.post("/api/verdicts/{verdict_id}/override", response_model=OverrideRead)
    def create_override(verdict_id: int, payload: OverrideCreate) -> OverrideRead:
        with session_scope(app.state.session_factory) as session:
            verdict = session.get(models.Verdict, verdict_id)
            if verdict is None:
                raise HTTPException(status_code=404, detail="verdict not found")
            row = models.Override(
                verdict_id=verdict_id,
                reviewer_comment=payload.reviewer_comment,
                new_verdict=payload.new_verdict,
            )
            session.add(row)
            session.flush()
            return OverrideRead(
                id=row.id,
                verdict_id=row.verdict_id,
                reviewer_comment=row.reviewer_comment,
                new_verdict=row.new_verdict,
                created_at=row.created_at,
            )

    @app.post("/api/qa", response_model=QAResponse)
    def ask_qa(payload: QARequest) -> QAResponse:
        result = app.state.qa.answer(payload.question)
        with session_scope(app.state.session_factory) as session:
            session.add(
                models.QAQuery(
                    question=payload.question,
                    answer=result.answer,
                    refused=result.refused,
                    cited_clauses=[clause.model_dump() for clause in result.cited_clauses],
                )
            )
        return QAResponse(
            answer=result.answer,
            refused=result.refused,
            refusal_reason=result.refusal_reason,
            cited_clauses=[
                {"doc_id": clause.doc_id, "section": clause.section, "quoted_text": clause.quoted_text}
                for clause in result.cited_clauses
            ],
        )

    @app.get("/api/retrieval/test")
    def retrieval_test(query: str, k: int = 5) -> list[dict[str, object]]:
        results = app.state.retrieval.retrieve(query=query, k=k)
        return [result.model_dump() for result in results]

    @app.get("/api/extraction/test")
    def extraction_test(path: str) -> dict[str, object]:
        outcome = app.state.extraction.extract_receipt(path)
        return outcome.model_dump()

    @app.get("/api/judgment/test")
    def judgment_test(path: str, trip_context: str = "") -> dict[str, object]:
        extraction_outcome = app.state.extraction.extract_receipt(path)
        judged = app.state.judgment.judge_line_item(
            extracted=extraction_outcome.extracted,
            extraction_confidence=extraction_outcome.confidence,
            trip_context=trip_context,
        )
        return {
            "extraction": extraction_outcome.model_dump(),
            "judgment": judged.model_dump(),
        }

    return app


app = create_app()


def _process_uploaded_file(
    session,
    submission: models.Submission,
    incoming: UploadFile,
    upload_dir: Path,
    extraction_service,
    judgment_service,
) -> LineItemRead:
    target_path = upload_dir / incoming.filename
    with target_path.open("wb") as handle:
        shutil.copyfileobj(incoming.file, handle)

    extraction_outcome = extraction_service.extract_receipt(str(target_path))
    judged = judgment_service.judge_line_item(
        extracted=extraction_outcome.extracted,
        extraction_confidence=extraction_outcome.confidence,
        trip_context=submission.trip_purpose,
    )

    line_item = models.LineItem(
        submission_id=submission.id,
        receipt_filename=incoming.filename,
        category=extraction_outcome.extracted.category,
        vendor=extraction_outcome.extracted.vendor,
        date=extraction_outcome.extracted.date,
        amount=extraction_outcome.extracted.amount,
        currency=extraction_outcome.extracted.currency,
        raw_extraction=extraction_outcome.model_dump(),
    )
    session.add(line_item)
    session.flush()

    verdict = models.Verdict(
        line_item_id=line_item.id,
        verdict=judged.verdict,
        reasoning=judged.reasoning,
        cited_clauses=[item.model_dump() for item in judged.cited_clauses],
        confidence=judged.confidence,
    )
    session.add(verdict)
    session.flush()
    submission.status = "reviewed"

    return LineItemRead(
        id=line_item.id,
        submission_id=line_item.submission_id,
        receipt_filename=line_item.receipt_filename,
        category=line_item.category,
        vendor=line_item.vendor,
        date=line_item.date,
        amount=line_item.amount,
        currency=line_item.currency,
        raw_extraction=line_item.raw_extraction,
        verdicts=[
            VerdictRead(
                id=verdict.id,
                line_item_id=verdict.line_item_id,
                verdict=verdict.verdict,
                reasoning=verdict.reasoning,
                cited_clauses=verdict.cited_clauses,
                confidence=verdict.confidence,
                created_at=verdict.created_at,
            )
        ],
    )
