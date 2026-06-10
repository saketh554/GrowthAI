from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.app.settings import Settings

Base = declarative_base()


def _sqlite_url(path: str) -> str:
    resolved = Path(path).resolve()
    return f"sqlite:///{resolved.as_posix()}"


def create_engine_and_factory(
    settings: Settings,
) -> tuple[Engine, sessionmaker[Session]]:
    engine = create_engine(
        _sqlite_url(settings.sqlite_path),
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, session_factory


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
