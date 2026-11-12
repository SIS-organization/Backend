"""Scheme pentru rezervări (ce intră și ce iese din API)."""

from datetime import datetime

from pydantic import computed_field, field_serializer

from app.core.time import to_api
from app.models.enums import BookingStatus
from app.schemas.common import CamelModel, PageMeta
from app.schemas.facility import FacilitySummary


class UserSummary(CamelModel):
    id: int
    first_name: str
    last_name: str


class BookingCreate(CamelModel):
    """Corpul pentru POST /bookings."""

    facility_id: int
    start_time: datetime
    end_time: datetime


class BookingUpdate(CamelModel):
    """Corpul pentru PATCH /bookings/{id} (mutarea rezervării în alt interval)."""

    start_time: datetime
    end_time: datetime


class BookingOut(CamelModel):
    """O rezervare în răspuns."""

    id: int
    facility: FacilitySummary
    user: UserSummary
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    early_released_at: datetime | None
    created_at: datetime

    @computed_field
    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() // 60)

    @field_serializer("start_time", "end_time", "early_released_at", "created_at")
    def _with_offset(self, value: datetime | None) -> str | None:
        local = to_api(value)
        return local.isoformat() if local else None


class BookingPage(PageMeta):
    items: list[BookingOut]
