from __future__ import annotations

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db import Base, create_engine_and_factory, session_scope
from backend.app import models  # noqa: F401
from backend.app.seed import seed_employees
from backend.app.settings import Settings, ensure_data_dirs


def init_persistence(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    ensure_data_dirs(settings)
    engine, session_factory = create_engine_and_factory(settings)
    Base.metadata.create_all(bind=engine)

    with session_scope(session_factory) as session:
        seed_employees(session, settings.submissions_dir)

    return engine, session_factory
