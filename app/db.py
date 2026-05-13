from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.settings import Settings, get_settings

Base = declarative_base()


def create_db_engine(settings: Settings | None = None):
    cfg = settings or get_settings()
    connect_args = {"check_same_thread": False} if cfg.database_url.startswith("sqlite") else {}
    return create_engine(cfg.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(settings: Settings | None = None):
    engine = create_db_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


SessionLocal = create_session_factory()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
