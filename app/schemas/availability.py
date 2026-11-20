"""Scheme pentru disponibilitatea unei facilități (schemele `Availability`)."""

import datetime as dt
from enum import Enum

from pydantic import Field, field_serializer

from app.core.time import to_api
from app.schemas.common import CamelModel


class SlotStatus(str, Enum):
    """Starea unui interval orar."""

    FREE = "free"  # se poate rezerva
    BOOKED = "booked"  # toate locurile sunt rezervate
    UNIVERSITY_COURSE = "university_course"  # curs USV
    UNIVERSITY_EVENT = "university_event"  # eveniment / altă activitate USV
    MAINTENANCE = "maintenance"  # mentenanță, reparații, curățenie
    PAST = "past"  # a început deja
    CLOSED = "closed"  # facilitate dezactivată


class SlotCell(CamelModel):
    """Un interval de o oră."""

    start_time: dt.datetime
    end_time: dt.datetime
    status: SlotStatus
    label: str | None = None
    bookable: bool  # poate fi rezervat acum
    booked_by_me: bool
    waitlist_available: bool  # se poate intra pe lista de așteptare
    waitlist_count: int  # câte persoane așteaptă acest interval
    # Specifice bazei noastre de date (nu apar în Swagger):
    capacity: int  # câte rezervări simultane suportă facilitatea
    free_spots: int  # câte locuri mai sunt libere

    @field_serializer("start_time", "end_time")
    def _with_offset(self, value: dt.datetime) -> str:
        return to_api(value).isoformat()


class DayAvailability(CamelModel):
    date: dt.date
    is_today: bool
    open_time: str = Field(alias="open")
    close_time: str = Field(alias="close")
    slots: list[SlotCell]


class AvailabilityOut(CamelModel):
    facility_id: int
    timezone: str
    from_date: dt.date = Field(alias="from")
    to_date: dt.date = Field(alias="to")
    generated_at: dt.datetime
    days: list[DayAvailability]

    @field_serializer("generated_at")
    def _with_offset(self, value: dt.datetime) -> str:
        return to_api(value).isoformat()
