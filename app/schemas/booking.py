"""Scheme pentru rezervări (conform schemele `Booking` din Swagger)."""

from datetime import datetime

from pydantic import Field, field_serializer

from app.core.time import to_api
from app.models.enums import BookingStatus, CancellationSource, UserRole
from app.schemas.common import CamelModel, PageMeta
from app.schemas.facility import FacilitySummary


class BookingUser(CamelModel):
    id: int
    name: str
    role: UserRole


class BookingCreate(CamelModel):
    """Corpul pentru POST /bookings."""

    facility_id: int
    start_time: datetime
    end_time: datetime
    # Acceptate ca în Swagger, dar încă neutilizate (plata și notițele vin mai târziu).
    allow_paid_extra: bool = False
    notes: str | None = Field(default=None, max_length=300)


class BookingUpdate(CamelModel):
    """Corpul pentru PATCH /bookings/{id} (mutarea rezervării în alt interval)."""

    start_time: datetime
    end_time: datetime


class CancelRequest(CamelModel):
    """Corpul (opțional) pentru POST /bookings/{id}/cancel."""

    reason: str | None = Field(default=None, max_length=300)


class BookingOut(CamelModel):
    """O rezervare în răspuns."""

    id: int
    code: str  # cod afișat în UI, ex. USV-0108-12
    facility: FacilitySummary
    user: BookingUser
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    status: BookingStatus
    cancelled_at: datetime | None = None
    cancelled_by: CancellationSource | None = None
    cancel_reason: str | None = None
    cancellable_until: datetime | None = None
    can_cancel: bool
    early_released_at: datetime | None = None
    # Setat când rezervarea a rezultat dintr-o mutare (lista de așteptare).
    replaced_booking_id: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "start_time",
        "end_time",
        "cancelled_at",
        "cancellable_until",
        "early_released_at",
        "created_at",
        "updated_at",
    )
    def _with_offset(self, value: datetime | None) -> str | None:
        local = to_api(value)
        return local.isoformat() if local else None


class BookingPage(PageMeta):
    items: list[BookingOut]


class CancelResult(CamelModel):
    booking: BookingOut
    quota_restored: bool  # cota lunară nu este implementată încă
    waitlist_notified: int
