"""Regulile de business pentru rezervări (cerința 3.6)."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnprocessableError,
)
from app.core.time import now_local, to_local_naive
from app.models import Booking, BookingStatus, User, UserRole
from app.models.enums import BlockReason
from app.repositories.blocked_slot_repository import BlockedSlotRepository
from app.repositories.booking_repository import BookingRepository, BookingScope
from app.repositories.facility_repository import FacilityRepository
from app.schemas.booking import BookingOut, BookingUser
from app.schemas.facility import FacilitySummary

# Motivele pentru care o facilitate nu poate fi folosită (nu e o activitate USV).
_MAINTENANCE_REASONS = {
    BlockReason.MAINTENANCE,
    BlockReason.REPAIR,
    BlockReason.CLEANING,
}


class BookingService:
    """Creare, citire, mutare și anulare de rezervări."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.bookings = BookingRepository(db)
        self.facilities = FacilityRepository(db)
        self.blocked_slots = BlockedSlotRepository(db)
        self.settings = get_settings()

    # ---------- CREATE ----------
    def create(
        self,
        user: User,
        facility_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Booking:
        start, end = to_local_naive(start_time), to_local_naive(end_time)
        self._validate_slot(start, end)
        self._ensure_slot_available(user.id, facility_id, start, end)

        booking = self.bookings.add(
            Booking(
                user_id=user.id,
                facility_id=facility_id,
                start_time=start,
                end_time=end,
            )
        )
        self.db.commit()
        return self._reload(booking.id)

    # ---------- READ ----------
    def get(self, user: User, booking_id: int) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise NotFoundError(f"Rezervarea {booking_id} nu există.")
        self._ensure_can_access(user, booking)
        return booking

    def list_for_user(
        self,
        user: User,
        scope: BookingScope,
        page: int,
        page_size: int,
        status: BookingStatus | None = None,
        facility_id: int | None = None,
    ) -> tuple[list[Booking], int]:
        return self.bookings.list_for_user(
            user.id, scope, now_local(), page, page_size, status, facility_id
        )

    def present(self, booking: Booking) -> BookingOut:
        """Rezervarea în forma din API (cu câmpurile calculate din Swagger)."""
        active = booking.status == BookingStatus.CONFIRMED
        cancellable_until = (
            booking.start_time - timedelta(hours=self.settings.min_cancel_notice_hours)
            if active
            else None
        )
        return BookingOut(
            id=booking.id,
            code=f"USV-{booking.start_time:%m%d}-{booking.id}",
            facility=FacilitySummary(
                id=booking.facility.id,
                name=booking.facility.name,
                campus=booking.facility.location,
            ),
            user=BookingUser(
                id=booking.user.id,
                name=f"{booking.user.first_name} {booking.user.last_name}",
                role=booking.user.role,
            ),
            start_time=booking.start_time,
            end_time=booking.end_time,
            duration_minutes=int(
                (booking.end_time - booking.start_time).total_seconds() // 60
            ),
            status=booking.status,
            # Rezervarea anulată nu mai poate fi modificată, deci `updated_at`
            # este chiar momentul anulării.
            cancelled_at=(
                booking.updated_at
                if booking.status == BookingStatus.CANCELLED
                else None
            ),
            cancellable_until=cancellable_until,
            can_cancel=cancellable_until is not None
            and now_local() <= cancellable_until,
            early_released_at=booking.early_released_at,
            created_at=booking.created_at,
            updated_at=booking.updated_at,
        )

    # ---------- UPDATE (mutare în alt interval) ----------
    def reschedule(
        self,
        user: User,
        booking_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Booking:
        booking = self.get(user, booking_id)
        self._ensure_active(booking, code="INVALID_BOOKING_STATE")
        self._ensure_notice(
            booking,
            code="MODIFICATION_WINDOW_EXPIRED",
            action="modificată",
        )

        start, end = to_local_naive(start_time), to_local_naive(end_time)
        self._validate_slot(start, end)
        self._ensure_slot_available(
            booking.user_id, booking.facility_id, start, end, exclude_id=booking.id
        )

        booking.start_time = start
        booking.end_time = end
        self.db.commit()
        return self._reload(booking.id)

    # ---------- DELETE (anulare = "soft delete") ----------
    def cancel(self, user: User, booking_id: int) -> Booking:
        booking = self.get(user, booking_id)
        self._ensure_active(booking, code="BOOKING_NOT_CANCELLABLE_IN_STATE")
        self._ensure_notice(
            booking,
            code="CANCELLATION_WINDOW_EXPIRED",
            action="anulată",
        )

        booking.status = BookingStatus.CANCELLED
        self.db.commit()
        return self._reload(booking.id)

    # ---------- reguli ----------
    def _validate_slot(self, start: datetime, end: datetime) -> None:
        """Verificări care nu au nevoie de baza de date."""
        s = self.settings
        if end <= start:
            raise UnprocessableError(
                "Ora de sfârșit trebuie să fie după ora de început.",
                code="INVALID_TIME_RANGE",
            )
        duration = int((end - start).total_seconds() // 60)
        if duration != s.slot_minutes:
            raise UnprocessableError(
                f"O rezervare durează exact {s.slot_minutes} de minute.",
                code="INVALID_TIME_RANGE",
            )
        if start.minute != 0 or start.second != 0 or start.microsecond != 0:
            raise UnprocessableError(
                "Rezervarea trebuie să înceapă la o oră fixă (ex. 10:00).",
                code="INVALID_TIME_RANGE",
            )
        if (
            start.date() != end.date()
            or start.time() < s.opening_time
            or end.time() > s.closing_time
        ):
            raise UnprocessableError(
                f"Programul este {s.opening_time:%H:%M}–{s.closing_time:%H:%M}.",
                code="OUTSIDE_OPENING_HOURS",
            )
        if start < now_local():
            raise UnprocessableError(
                "Nu se pot face rezervări în trecut.", code="SLOT_IN_THE_PAST"
            )

    def _ensure_slot_available(
        self,
        user_id: int,
        facility_id: int,
        start: datetime,
        end: datetime,
        exclude_id: int | None = None,
    ) -> None:
        """Verificări pe baza de date; blochează facilitatea până la commit."""
        facility = self.facilities.get_for_update(facility_id)
        if facility is None:
            raise NotFoundError(f"Facilitatea {facility_id} nu există.")
        if not facility.is_active:
            raise ConflictError(
                f"{facility.name} nu este disponibilă momentan.",
                code="FACILITY_UNDER_MAINTENANCE",
            )

        blocked = self.blocked_slots.find_overlapping(facility_id, start, end)
        if blocked is not None:
            if blocked.reason in _MAINTENANCE_REASONS:
                raise ConflictError(
                    f"{facility.name} este în mentenanță în acest interval.",
                    code="FACILITY_UNDER_MAINTENANCE",
                )
            raise ConflictError(
                "Intervalul este ocupat de o activitate a universității.",
                code="SLOT_BLOCKED_BY_UNIVERSITY_ACTIVITY",
            )

        if self.bookings.user_has_overlapping(
            user_id, facility_id, start, end, exclude_id
        ):
            raise ConflictError(
                "Ai deja o rezervare la această facilitate în acest interval.",
                code="USER_ALREADY_BOOKED",
            )

        taken = self.bookings.count_overlapping(facility_id, start, end, exclude_id)
        if taken >= facility.capacity:
            raise ConflictError(
                "Intervalul este deja rezervat.",
                code="SLOT_ALREADY_BOOKED",
                # Lista de așteptare nu este implementată încă.
                extensions={"waitlistAvailable": False},
            )

    def _ensure_can_access(self, user: User, booking: Booking) -> None:
        if booking.user_id != user.id and user.role != UserRole.ADMINISTRATOR:
            raise ForbiddenError("Nu ai acces la această rezervare.")

    def _ensure_active(self, booking: Booking, code: str) -> None:
        if booking.status != BookingStatus.CONFIRMED:
            raise ConflictError("Rezervarea nu mai este activă.", code=code)

    def _ensure_notice(self, booking: Booking, code: str, action: str) -> None:
        """Rezervarea poate fi schimbată doar cu cel puțin N ore înainte."""
        hours = self.settings.min_cancel_notice_hours
        if booking.start_time - now_local() < timedelta(hours=hours):
            raise UnprocessableError(
                f"Rezervarea poate fi {action} cu cel puțin {hours} ore înainte.",
                code=code,
            )

    def _reload(self, booking_id: int) -> Booking:
        """Reîncarcă rezervarea cu facilitatea și utilizatorul (pentru răspuns)."""
        self.db.expire_all()
        booking = self.bookings.get(booking_id)
        assert booking is not None
        return booking
