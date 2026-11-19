"""Endpoint-uri pentru facilități."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.exceptions import AppError
from app.routers.dependencies import CurrentUser, DbSession
from app.schemas.availability import AvailabilityOut
from app.schemas.facility import FacilityPage
from app.services.facility_catalog import AmenityCode, SportCode
from app.services.facility_service import FacilityService

router = APIRouter(prefix="/facilities", tags=["Facilities"])


def _parse_amenities(raw: str | None) -> list[AmenityCode]:
    """`amenities=showers,changing_rooms` -> [AmenityCode, ...]."""
    if not raw:
        return []
    try:
        return [AmenityCode(code.strip()) for code in raw.split(",") if code.strip()]
    except ValueError as exc:
        valid = ", ".join(a.value for a in AmenityCode)
        raise AppError(
            f"Dotare necunoscută. Valori permise: {valid}.", code="VALIDATION_ERROR"
        ) from exc


@router.get("", response_model=FacilityPage, summary="Catalogul de facilități")
def list_facilities(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(description="Nume facilitate sau sport")] = None,
    sport: Annotated[SportCode | None, Query(description="Cod sport")] = None,
    amenities: Annotated[
        str | None, Query(description="Dotări obligatorii, separate prin virgulă")
    ] = None,
    date: Annotated[
        dt.date | None, Query(description="Data pentru „următorul interval liber”")
    ] = None,
    include_unavailable: Annotated[bool, Query(alias="includeUnavailable")] = True,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="pageSize")] = 20,
) -> FacilityPage:
    return FacilityService(db).list_page(
        q=q,
        sport=sport,
        amenities=_parse_amenities(amenities),
        on_date=date,
        include_unavailable=include_unavailable,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{facility_id}/availability",
    response_model=AvailabilityOut,
    summary="Calendarul de disponibilitate",
)
def get_availability(
    facility_id: int,
    user: CurrentUser,
    db: DbSession,
    date_from: Annotated[
        dt.date | None, Query(alias="from", description="Prima zi (YYYY-MM-DD)")
    ] = None,
    date_to: Annotated[
        dt.date | None, Query(alias="to", description="Ultima zi (YYYY-MM-DD)")
    ] = None,
) -> AvailabilityOut:
    """Implicit: 7 zile începând de azi. Maximum 14 zile."""
    return FacilityService(db).availability(user, facility_id, date_from, date_to)
