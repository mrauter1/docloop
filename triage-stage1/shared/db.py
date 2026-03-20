from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings


def get_database_url(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return resolved.database_url


def make_engine(settings: Settings | None = None, url: str | None = None) -> Engine:
    database_url = url or get_database_url(settings)
    return create_engine(database_url, future=True)


def make_session_factory(
    settings: Settings | None = None,
    url: str | None = None,
) -> sessionmaker[Session]:
    engine = make_engine(settings=settings, url=url)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
