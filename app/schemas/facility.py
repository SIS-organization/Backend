"""Scheme pentru facilități (conform schemei `Facility` din Swagger)."""

import datetime as dt
from enum import Enum

from pydantic import field_serializer

from app.core.time import to_api
from app.models.enums import FacilityType
from app.schemas.common import CamelModel, PageMeta


class Sport(CamelModel):
    code: str
    label: str


class Amenity(CamelModel):
    code: str
    label: str


class TimeSlot(CamelModel):
    """Un interval de timp, cu offset față de UTC (ex. +02:00)."""

    start_time: dt.datetime
    end_time: dt.datetime

    @field_serializer("start_time", "end_time")
    def _with_offset(self, value: dt.datetime) -> str:
        return to_api(value).isoformat()


class FacilityStatus(str, Enum):
    OPERATIONAL = "operational"
    UNDER_MAINTENANCE = "under_maintenance"
    UNIVERSITY_ACTIVITY = "university_activity"
    CLOSED = "closed"


class FacilitySummary(CamelModel):
    """Facilitatea, în forma scurtă folosită în interiorul unei rezervări."""

    id: int
    name: str
    campus: str


class FacilityOut(FacilitySummary):
    """Facilitatea completă."""

    description: str
    sports: list[Sport]
    amenities: list[Amenity]
    status: FacilityStatus
    status_note: str | None = None
    opening_time: str
    closing_time: str
    slot_duration_minutes: int
    timezone: str
    next_free_slot: TimeSlot | None = None
    # Specifice bazei noastre de date (nu apar în Swagger):
    type: FacilityType
    capacity: int  # rezervări simultane (ex. 4 culoare la bazin)


class FacilityPage(PageMeta):
    items: list[FacilityOut]
