"""Endpoint-uri pentru rezervări: CRUD (cerința 3.6)."""

import math
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status

from app.models import BookingStatus
from app.repositories.booking_repository import BookingScope
from app.routers.dependencies import CurrentUser, DbSession
from app.schemas.booking import (
    BookingCreate,
    BookingOut,
    BookingPage,
    BookingUpdate,
    CancelRequest,
    CancelResult,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Creează o rezervare",
)
def create_booking(
    body: BookingCreate,
    response: Response,
    user: CurrentUser,
    db: DbSession,
    # Acceptat ca în Swagger. Un dublu-click este oprit oricum de regula
    # „ai deja o rezervare în acest interval" (409 USER_ALREADY_BOOKED).
    idempotency_key: Annotated[str | None, Header()] = None,
) -> BookingOut:
    service = BookingService(db)
    booking = service.create(user, body.facility_id, body.start_time, body.end_time)
    response.headers["Location"] = f"/v1/bookings/{booking.id}"
    return service.present(booking)


@router.get(
    "",
    response_model=BookingPage,
    summary="Rezervările mele (upcoming / history / all)",
)
def list_bookings(
    user: CurrentUser,
    db: DbSession,
    scope: BookingScope = BookingScope.UPCOMING,
    booking_status: Annotated[BookingStatus | None, Query(alias="status")] = None,
    facility_id: Annotated[int | None, Query(alias="facilityId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="pageSize")] = 20,
) -> BookingPage:
    service = BookingService(db)
    items, total = service.list_for_user(
        user, scope, page, page_size, booking_status, facility_id
    )
    return BookingPage(
        items=[service.present(b) for b in items],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size),
    )


@router.get("/{booking_id}", response_model=BookingOut, summary="Detalii rezervare")
def get_booking(booking_id: int, user: CurrentUser, db: DbSession) -> BookingOut:
    service = BookingService(db)
    return service.present(service.get(user, booking_id))


@router.patch(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Mută rezervarea în alt interval",
)
def reschedule_booking(
    booking_id: int, body: BookingUpdate, user: CurrentUser, db: DbSession
) -> BookingOut:
    service = BookingService(db)
    booking = service.reschedule(user, booking_id, body.start_time, body.end_time)
    return service.present(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=CancelResult,
    summary="Anulează rezervarea",
)
def cancel_booking(
    booking_id: int,
    user: CurrentUser,
    db: DbSession,
    # Motivul (opțional) se salvează în `bookings.cancel_reason`.
    body: CancelRequest | None = None,
) -> CancelResult:
    service = BookingService(db)
    booking, notified = service.cancel(user, booking_id, body.reason if body else None)
    return CancelResult(
        booking=service.present(booking),
        quota_restored=False,
        waitlist_notified=notified,
    )
