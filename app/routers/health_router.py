"""Verificarea stării aplicației."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.routers.dependencies import DbSession

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Starea aplicației")
def health(db: DbSession) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        database = "down"
    return {
        "status": "ok" if database == "up" else "degraded",
        "version": get_settings().app_version,
        "dependencies": {"database": database},
    }
