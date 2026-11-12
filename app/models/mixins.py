"""Coloane comune mai multor tabele."""

from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.orm import Mapped, mapped_column

NOW_LOCAL = text("(now() AT TIME ZONE 'Europe/Bucharest')")


class TimestampMixin:
    """created_at / updated_at (updated_at este setat de un trigger din DB)."""

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=NOW_LOCAL)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=NOW_LOCAL)
