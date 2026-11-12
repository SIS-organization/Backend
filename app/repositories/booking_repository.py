"""Acces la tabela `bookings` (doar interogări SQL, fără reguli de business)."""

from datetime import datetime
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Booking, BookingStatus


class BookingScope(str, Enum):
    """Ce rezervări să returneze lista."""

    UPCOMING = "upcoming"
    HISTORY = "history"
    ALL = "all"


class BookingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, booking: Booking) -> Booking:
        self.db.add(booking)
        self.db.flush()
        return booking

    def get(self, booking_id: int) -> Booking | None:
        return self.db.scalar(
            select(Booking)
            .options(joinedload(Booking.facility), joinedload(Booking.user))
            .where(Booking.id == booking_id)
        )

    def list_for_user(
        self,
        user_id: int,
        scope: BookingScope,
        now: datetime,
        page: int,
        page_size: int,
    ) -> tuple[list[Booking], int]:
        """Rezervările unui utilizator, paginate. Returnează (elemente, total)."""
        is_upcoming = (Booking.status == BookingStatus.CONFIRMED) & (
            Booking.end_time > now
        )
        query = select(Booking).where(Booking.user_id == user_id)
        if scope is BookingScope.UPCOMING:
            query = query.where(is_upcoming).order_by(Booking.start_time)
        elif scope is BookingScope.HISTORY:
            query = query.where(~is_upcoming).order_by(Booking.start_time.desc())
        else:
            query = query.order_by(Booking.start_time.desc())

        total = self.db.scalar(select(func.count()).select_from(query.subquery()))
        items = self.db.scalars(
            query.options(joinedload(Booking.facility), joinedload(Booking.user))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique()
        return list(items), total or 0

    def count_overlapping(
        self,
        facility_id: int,
        start: datetime,
        end: datetime,
        exclude_id: int | None = None,
    ) -> int:
        """Câte rezervări active se suprapun cu [start, end) la o facilitate."""
        query = select(func.count()).where(
            Booking.facility_id == facility_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time < end,
            Booking.end_time > start,
        )
        if exclude_id is not None:
            query = query.where(Booking.id != exclude_id)
        return self.db.scalar(query) or 0

    def user_has_overlapping(
        self,
        user_id: int,
        facility_id: int,
        start: datetime,
        end: datetime,
        exclude_id: int | None = None,
    ) -> bool:
        """Utilizatorul are deja o rezervare activă aici, în acel interval?"""
        query = select(func.count()).where(
            Booking.user_id == user_id,
            Booking.facility_id == facility_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.start_time < end,
            Booking.end_time > start,
        )
        if exclude_id is not None:
            query = query.where(Booking.id != exclude_id)
        return (self.db.scalar(query) or 0) > 0
