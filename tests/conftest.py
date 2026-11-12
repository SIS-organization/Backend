"""Configurarea testelor.

Testele rulează pe un PostgreSQL real (aplicația folosește tipuri enum și
triggere PostgreSQL), într-o bază de date separată al cărei nume se termină în
`_test`. Schema și datele de test se creează din `database/*.sql`.
"""

import os
import re
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent


def _read_env_file_value(name: str) -> str | None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return None
    match = re.search(rf"^{name}=(.+)$", env_file.read_text(), re.MULTILINE)
    return match.group(1).strip() if match else None


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or _read_env_file_value(
        "TEST_DATABASE_URL"
    )
    if not url:
        base = os.environ.get("DATABASE_URL") or _read_env_file_value("DATABASE_URL")
        if not base:
            pytest.exit("Setează DATABASE_URL (în .env) sau TEST_DATABASE_URL.")
        parsed = make_url(base)
        url = parsed.set(database=f"{parsed.database}_test").render_as_string(
            hide_password=False
        )
    if not make_url(url).database.endswith("_test"):
        pytest.exit("Baza de date pentru teste trebuie să se termine cu '_test'.")
    return url


TEST_URL = _test_database_url()
# Setat ÎNAINTE de importul aplicației, ca engine-ul să folosească baza de test.
os.environ["DATABASE_URL"] = TEST_URL

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Booking, BookingStatus  # noqa: E402

# "Acum" fix în teste: luni, 7 ianuarie 2030, 09:00 (ora locală).
FAKE_NOW = datetime(2030, 1, 7, 9, 0)


@pytest.fixture(scope="session", autouse=True)
def database_schema():
    """Creează tabelele și datele de test o singură dată pe rulare."""
    dsn = TEST_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn, autocommit=True) as conn:
        for script in ("schema.sql", "seed.sql"):
            conn.execute((ROOT / "database" / script).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_bookings():
    """Fiecare test pornește fără rezervări sau blocări, cu facilitățile active."""
    with SessionLocal() as db:
        db.execute(text("TRUNCATE bookings, blocked_slots RESTART IDENTITY CASCADE"))
        db.execute(text("UPDATE facilities SET is_active = true"))
        db.commit()


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr("app.services.booking_service.now_local", lambda: FAKE_NOW)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


# Ids din seed.sql
ANDREI, DARIA, ELENA, ADMIN, VLAD = 1, 2, 3, 4, 5
TEREN, FITNESS, BAZIN, SALA = 1, 2, 3, 4


def headers(user_id: int) -> dict[str, str]:
    return {"X-User-Id": str(user_id)}


def slot(day: int = 8, hour: int = 10) -> dict[str, str]:
    """Un interval de 1 oră pe ianuarie 2030 (cu offset +02:00)."""
    return {
        "startTime": f"2030-01-{day:02d}T{hour:02d}:00:00+02:00",
        "endTime": f"2030-01-{day:02d}T{hour + 1:02d}:00:00+02:00",
    }


def make_booking(
    db,
    user_id: int = ANDREI,
    facility_id: int = TEREN,
    start: datetime = datetime(2030, 1, 8, 10),
    status: BookingStatus = BookingStatus.CONFIRMED,
) -> Booking:
    """Inserează direct o rezervare în DB (ocolește regulile)."""
    booking = Booking(
        user_id=user_id,
        facility_id=facility_id,
        start_time=start,
        end_time=start.replace(hour=start.hour + 1),
        status=status,
    )
    db.add(booking)
    db.commit()
    return booking
