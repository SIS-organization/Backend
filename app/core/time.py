"""Ore locale.

În baza de date orele sunt salvate ca ora locală (Europe/Bucharest), fără fus
orar. Aici facem conversia între ora din API (ISO 8601 cu offset) și cea din DB.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def local_tz() -> ZoneInfo:
    """Fusul orar al campusului."""
    return ZoneInfo(get_settings().timezone)


def now_local() -> datetime:
    """Ora curentă locală, fără fus orar (formatul din baza de date)."""
    return datetime.now(local_tz()).replace(tzinfo=None)


def to_local_naive(value: datetime) -> datetime:
    """Din ora primită în API în ora locală fără fus (pentru DB).

    O oră fără offset este considerată deja ora locală.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(local_tz()).replace(tzinfo=None)


def to_api(value: datetime | None) -> datetime | None:
    """Din ora locală din DB în ora cu offset (ex. +02:00) pentru răspuns."""
    if value is None:
        return None
    return value.replace(tzinfo=local_tz())
