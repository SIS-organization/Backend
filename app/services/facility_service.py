"""Facilitățile: listă și disponibilitate (doar citire)."""

import datetime as dt
import math
import unicodedata

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.core.time import now_local
from app.models import BlockedSlot, BlockReason, Booking, Facility, User
from app.repositories.blocked_slot_repository import BlockedSlotRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.facility_repository import FacilityRepository
from app.schemas.availability import (
    AvailabilityOut,
    DayAvailability,
    SlotCell,
    SlotStatus,
)
from app.schemas.facility import (
    Amenity,
    FacilityOut,
    FacilityPage,
    FacilityStatus,
    Sport,
    TimeSlot,
)
from app.services.facility_catalog import (
    AMENITY_LABELS,
    PROFILES,
    SPORT_LABELS,
    AmenityCode,
    SportCode,
)

MAX_RANGE_DAYS = 14
NEXT_FREE_LOOKAHEAD_DAYS = 14
_MAINTENANCE_REASONS = {
    BlockReason.MAINTENANCE,
    BlockReason.REPAIR,
    BlockReason.CLEANING,
}


def _fold(text: str) -> str:
    """Text fără diacritice și litere mici (pentru căutare: „inot" găsește „Înot")."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


class FacilityService:
    def __init__(self, db: Session) -> None:
        self.facilities = FacilityRepository(db)
        self.bookings = BookingRepository(db)
        self.blocked_slots = BlockedSlotRepository(db)
        self.settings = get_settings()

    # ---------- listă ----------
    def list_page(
        self,
        *,
        q: str | None,
        sport: SportCode | None,
        amenities: list[AmenityCode],
        on_date: dt.date | None,
        include_unavailable: bool,
        page: int,
        page_size: int,
    ) -> FacilityPage:
        now = now_local()
        matching: list[FacilityOut] = []
        for facility in self.facilities.list_all():
            profile = PROFILES[facility.type]
            if sport is not None and sport not in profile.sports:
                continue
            if not set(amenities) <= set(profile.amenities):
                continue
            if q and not self._matches_text(q, facility):
                continue
            out = self._to_out(facility, now, on_date)
            if not include_unavailable and out.status != FacilityStatus.OPERATIONAL:
                continue
            matching.append(out)

        total = len(matching)
        start = (page - 1) * page_size
        return FacilityPage(
            items=matching[start : start + page_size],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=math.ceil(total / page_size),
        )

    @staticmethod
    def _matches_text(query: str, facility: Facility) -> bool:
        needle = _fold(query.strip())
        haystack = [facility.name] + [
            SPORT_LABELS[s] for s in PROFILES[facility.type].sports
        ]
        return any(needle in _fold(text) for text in haystack)

    def _to_out(
        self, facility: Facility, now: dt.datetime, on_date: dt.date | None
    ) -> FacilityOut:
        s = self.settings
        profile = PROFILES[facility.type]
        status, note = self._current_status(facility, now)
        return FacilityOut(
            id=facility.id,
            name=facility.name,
            campus=facility.location,
            description=profile.description,
            sports=[Sport(code=c.value, label=SPORT_LABELS[c]) for c in profile.sports],
            amenities=[
                Amenity(code=c.value, label=AMENITY_LABELS[c])
                for c in profile.amenities
            ],
            status=status,
            status_note=note,
            opening_time=f"{s.opening_time:%H:%M}",
            closing_time=f"{s.closing_time:%H:%M}",
            slot_duration_minutes=s.slot_minutes,
            timezone=s.timezone,
            next_free_slot=self._next_free_slot(facility, now, on_date),
            type=facility.type,
            capacity=facility.capacity,
        )

    def _current_status(
        self, facility: Facility, now: dt.datetime
    ) -> tuple[FacilityStatus, str | None]:
        if not facility.is_active:
            return FacilityStatus.CLOSED, None
        block = self.blocked_slots.find_overlapping(
            facility.id, now, now + dt.timedelta(minutes=1)
        )
        if block is None:
            return FacilityStatus.OPERATIONAL, None
        note = f"Astăzi {block.start_time:%H:%M}–{block.end_time:%H:%M}"
        if block.start_time.date() != block.end_time.date():
            note = f"Până la {block.end_time:%d.%m %H:%M}"
        if block.reason in _MAINTENANCE_REASONS:
            return FacilityStatus.UNDER_MAINTENANCE, note
        return FacilityStatus.UNIVERSITY_ACTIVITY, note

    def _next_free_slot(
        self, facility: Facility, now: dt.datetime, on_date: dt.date | None
    ) -> TimeSlot | None:
        """Primul interval liber, începând de azi sau de la data cerută."""
        if not facility.is_active:
            return None
        first_day = max(on_date, now.date()) if on_date else now.date()
        range_start = dt.datetime.combine(first_day, dt.time.min)
        range_end = range_start + dt.timedelta(days=NEXT_FREE_LOOKAHEAD_DAYS)
        bookings = self.bookings.list_active_overlapping(
            facility.id, range_start, range_end
        )
        blocked = self.blocked_slots.list_overlapping(
            facility.id, range_start, range_end
        )
        step = dt.timedelta(minutes=self.settings.slot_minutes)
        for offset in range(NEXT_FREE_LOOKAHEAD_DAYS):
            for start in self._slot_starts(first_day + dt.timedelta(days=offset)):
                status, _, _ = self._slot_state(
                    facility, bookings, blocked, start, start + step, now
                )
                if status is SlotStatus.FREE:
                    return TimeSlot(start_time=start, end_time=start + step)
        return None

    # ---------- disponibilitate ----------
    def availability(
        self,
        user: User,
        facility_id: int,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> AvailabilityOut:
        """Starea fiecărui interval orar, între două date (inclusiv)."""
        now = now_local()
        date_from = date_from or now.date()
        date_to = date_to or date_from + dt.timedelta(days=6)
        if date_to < date_from:
            raise AppError(
                "Data `to` nu poate fi înaintea datei `from`.", code="VALIDATION_ERROR"
            )
        if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
            raise AppError(
                f"Intervalul poate avea cel mult {MAX_RANGE_DAYS} zile.",
                code="VALIDATION_ERROR",
            )

        facility = self.facilities.get(facility_id)
        if facility is None:
            raise NotFoundError(f"Facilitatea {facility_id} nu există.")

        range_start = dt.datetime.combine(date_from, dt.time.min)
        range_end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time.min)
        bookings = self.bookings.list_active_overlapping(
            facility_id, range_start, range_end
        )
        blocked = self.blocked_slots.list_overlapping(
            facility_id, range_start, range_end
        )
        mine = [b for b in bookings if b.user_id == user.id]

        s = self.settings
        step = dt.timedelta(minutes=s.slot_minutes)
        days: list[DayAvailability] = []
        day = date_from
        while day <= date_to:
            cells = []
            for start in self._slot_starts(day):
                end = start + step
                status, free, label = self._slot_state(
                    facility, bookings, blocked, start, end, now
                )
                cells.append(
                    SlotCell(
                        start_time=start,
                        end_time=end,
                        status=status,
                        label=label,
                        bookable=status is SlotStatus.FREE,
                        booked_by_me=any(
                            b.start_time < end and b.end_time > start for b in mine
                        ),
                        waitlist_available=False,
                        waitlist_count=0,
                        capacity=facility.capacity,
                        free_spots=free,
                    )
                )
            days.append(
                DayAvailability(
                    date=day,
                    is_today=day == now.date(),
                    open=f"{s.opening_time:%H:%M}",
                    close=f"{s.closing_time:%H:%M}",
                    slots=cells,
                )
            )
            day += dt.timedelta(days=1)

        return AvailabilityOut(
            facility_id=facility.id,
            timezone=s.timezone,
            from_date=date_from,
            to_date=date_to,
            generated_at=now,
            days=days,
        )

    def _slot_starts(self, day: dt.date) -> list[dt.datetime]:
        """Orele de început dintr-o zi, conform programului."""
        step = dt.timedelta(minutes=self.settings.slot_minutes)
        current = dt.datetime.combine(day, self.settings.opening_time)
        closing = dt.datetime.combine(day, self.settings.closing_time)
        starts = []
        while current + step <= closing:
            starts.append(current)
            current += step
        return starts

    @staticmethod
    def _slot_state(
        facility: Facility,
        bookings: list[Booking],
        blocked: list[BlockedSlot],
        start: dt.datetime,
        end: dt.datetime,
        now: dt.datetime,
    ) -> tuple[SlotStatus, int, str | None]:
        """(stare, locuri libere, etichetă) pentru un interval."""
        if start < now:
            return SlotStatus.PAST, 0, None
        if not facility.is_active:
            return SlotStatus.CLOSED, 0, "Închis"
        for block in blocked:
            if block.start_time < end and block.end_time > start:
                if block.reason in _MAINTENANCE_REASONS:
                    return SlotStatus.MAINTENANCE, 0, "Mentenanță"
                if block.reason is BlockReason.UNIVERSITY_COURSE:
                    return SlotStatus.UNIVERSITY_COURSE, 0, "Curs USV"
                return SlotStatus.UNIVERSITY_EVENT, 0, "Eveniment USV"
        taken = sum(1 for b in bookings if b.start_time < end and b.end_time > start)
        free = max(facility.capacity - taken, 0)
        if free > 0:
            return SlotStatus.FREE, free, None
        return SlotStatus.BOOKED, 0, "Rezervat"
