"""Scheme pentru lista de așteptare (schemele `Waitlist*` din Swagger)."""

from datetime import datetime

from pydantic import field_serializer

from app.core.time import to_api
from app.models.enums import WaitlistStatus
from app.schemas.common import CamelModel


class WaitlistCreate(CamelModel):
    """Corpul pentru POST /waitlist."""

    facility_id: int
    start_time: datetime
    end_time: datetime
    # Dacă este setat, la acceptarea ofertei această rezervare este mutată
    # (înlocuită), nu se adaugă una nouă.
    replace_booking_id: int | None = None


class WaitlistFacility(CamelModel):
    id: int
    name: str


class WaitlistUser(CamelModel):
    id: int
    name: str


class WaitlistEntryOut(CamelModel):
    """O intrare pe lista de așteptare, în răspuns."""

    id: int
    facility: WaitlistFacility
    user: WaitlistUser
    start_time: datetime
    end_time: datetime
    # Locul în listă (1 = primul). Doar pentru intrările încă deschise.
    position: int | None = None
    status: WaitlistStatus
    replace_booking_id: int | None = None
    offer_expires_at: datetime | None = None
    created_at: datetime

    @field_serializer("start_time", "end_time", "offer_expires_at", "created_at")
    def _with_offset(self, value: datetime | None) -> str | None:
        local = to_api(value)
        return local.isoformat() if local else None
