from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base, create_engine_and_factory, session_scope
from backend.app import models  # noqa: F401
from backend.app.extraction import ExtractionService
from backend.app.judge import JudgmentService
from backend.app.retrieval import RetrievalService
from backend.app.seed import seed_employees
from backend.app.settings import Settings, ensure_data_dirs


def init_persistence(
    settings: Settings,
) -> tuple[Engine, sessionmaker[Session], RetrievalService, ExtractionService, JudgmentService]:
    ensure_data_dirs(settings)
    engine, session_factory = create_engine_and_factory(settings)
    Base.metadata.create_all(bind=engine)

    with session_scope(session_factory) as session:
        seed_employees(session, settings.submissions_dir)

    retrieval = RetrievalService(settings)
    retrieval.build_index_if_missing()
    extraction = ExtractionService(settings)
    judgment = JudgmentService(settings, retrieval)

    return engine, session_factory, retrieval, extraction, judgment
