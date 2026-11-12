"""Conexiunea la baza de date (SQLAlchemy) și sesiunea per cerere."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clasa de bază pentru toate modelele (tabelele)."""


def get_db() -> Generator[Session, None, None]:
    """Dependență FastAPI: oferă o sesiune și o închide la final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
