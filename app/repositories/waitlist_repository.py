"""Acces la tabela `waitlist_entries` (doar interogări SQL, fără reguli de business)."""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import WaitlistEntry, WaitlistStatus

# Intrările care încă așteaptă (sunt „pe listă").
OPEN_STATUSES = (WaitlistStatus.ACTIVE, WaitlistStatus.OFFERED)


class WaitlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entry: WaitlistEntry) -> WaitlistEntry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def get(self, entry_id: int) -> WaitlistEntry | None:
        return self.db.scalar(
            select(WaitlistEntry)
            .options(joinedload(WaitlistEntry.facility), joinedload(WaitlistEntry.user))
            .where(WaitlistEntry.id == entry_id)
        )

    def list_for_user(
        self, user_id: int, status: WaitlistStatus | None = None
    ) -> list[WaitlistEntry]:
        query = (
            select(WaitlistEntry)
            .options(joinedload(WaitlistEntry.facility), joinedload(WaitlistEntry.user))
            .where(WaitlistEntry.user_id == user_id)
            .order_by(WaitlistEntry.start_time, WaitlistEntry.id)
        )
        if status is not None:
            query = query.where(WaitlistEntry.status == status)
        return list(self.db.scalars(query))

    def find_open(
        self, user_id: int, facility_id: int, start: datetime
    ) -> WaitlistEntry | None:
        """Intrarea încă deschisă a utilizatorului pe acest interval (dacă există)."""
        return self.db.scalars(
            select(WaitlistEntry).where(
                WaitlistEntry.user_id == user_id,
                WaitlistEntry.facility_id == facility_id,
                WaitlistEntry.start_time == start,
                WaitlistEntry.status.in_(OPEN_STATUSES),
            )
        ).first()

    def position(self, entry: WaitlistEntry) -> int:
        """Locul în listă (1 = primul), după ordinea înscrierii."""
        ahead = self.db.scalar(
            select(func.count()).where(
                WaitlistEntry.facility_id == entry.facility_id,
                WaitlistEntry.start_time == entry.start_time,
                WaitlistEntry.status.in_(OPEN_STATUSES),
                WaitlistEntry.id < entry.id,
            )
        )
        return (ahead or 0) + 1

    def next_active(self, facility_id: int, start: datetime) -> WaitlistEntry | None:
        """Primul din listă care încă nu a primit o ofertă."""
        return self.db.scalars(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.facility_id == facility_id,
                WaitlistEntry.start_time == start,
                WaitlistEntry.status == WaitlistStatus.ACTIVE,
            )
            .order_by(WaitlistEntry.id)
            .limit(1)
        ).first()

    def count_offered(self, facility_id: int, start: datetime) -> int:
        """Câte oferte așteaptă un răspuns pe acest interval."""
        return (
            self.db.scalar(
                select(func.count()).where(
                    WaitlistEntry.facility_id == facility_id,
                    WaitlistEntry.start_time == start,
                    WaitlistEntry.status == WaitlistStatus.OFFERED,
                )
            )
            or 0
        )

    def list_due(self, now: datetime) -> list[WaitlistEntry]:
        """Oferte expirate și intrări al căror interval a început deja."""
        return list(
            self.db.scalars(
                select(WaitlistEntry)
                .where(
                    WaitlistEntry.status.in_(OPEN_STATUSES),
                    or_(
                        WaitlistEntry.start_time <= now,
                        (WaitlistEntry.status == WaitlistStatus.OFFERED)
                        & (WaitlistEntry.offer_expires_at <= now),
                    ),
                )
                .order_by(WaitlistEntry.id)
            )
        )

    def list_open_replacing(
        self, booking_id: int, exclude_id: int | None = None
    ) -> list[WaitlistEntry]:
        """Intrările deschise care ar muta aceeași rezervare."""
        query = select(WaitlistEntry).where(
            WaitlistEntry.replace_booking_id == booking_id,
            WaitlistEntry.status.in_(OPEN_STATUSES),
        )
        if exclude_id is not None:
            query = query.where(WaitlistEntry.id != exclude_id)
        return list(self.db.scalars(query))

    def count_open_by_slot(
        self, facility_id: int, start: datetime, end: datetime
    ) -> dict[datetime, int]:
        """Câte persoane așteaptă fiecare interval al facilității, în [start, end)."""
        rows = self.db.execute(
            select(WaitlistEntry.start_time, func.count())
            .where(
                WaitlistEntry.facility_id == facility_id,
                WaitlistEntry.status.in_(OPEN_STATUSES),
                WaitlistEntry.start_time >= start,
                WaitlistEntry.start_time < end,
            )
            .group_by(WaitlistEntry.start_time)
        )
        return {start_time: count for start_time, count in rows}
