"""Endpoint-uri pentru rezervări: CRUD (cerința 3.6)."""

import math
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.repositories.booking_repository import BookingScope
from app.routers.dependencies import CurrentUser, DbSession
from app.schemas.booking import (
    BookingCreate,
    BookingOut,
    BookingPage,
    BookingUpdate,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post(
    "",
    response_model=BookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Creează o rezervare",
)
def create_booking(body: BookingCreate, user: CurrentUser, db: DbSession) -> BookingOut:
    booking = BookingService(db).create(
        user, body.facility_id, body.start_time, body.end_time
    )
    return BookingOut.model_validate(booking)


@router.get(
    "",
    response_model=BookingPage,
    summary="Rezervările mele (upcoming / history / all)",
)
def list_bookings(
    user: CurrentUser,
    db: DbSession,
    scope: BookingScope = BookingScope.UPCOMING,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="pageSize")] = 20,
) -> BookingPage:
    items, total = BookingService(db).list_for_user(user, scope, page, page_size)
    return BookingPage(
        items=[BookingOut.model_validate(b) for b in items],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size),
    )


@router.get("/{booking_id}", response_model=BookingOut, summary="Detalii rezervare")
def get_booking(booking_id: int, user: CurrentUser, db: DbSession) -> BookingOut:
    return BookingOut.model_validate(BookingService(db).get(user, booking_id))


@router.patch(
    "/{booking_id}",
    response_model=BookingOut,
    summary="Mută rezervarea în alt interval",
)
def reschedule_booking(
    booking_id: int, body: BookingUpdate, user: CurrentUser, db: DbSession
) -> BookingOut:
    booking = BookingService(db).reschedule(
        user, booking_id, body.start_time, body.end_time
    )
    return BookingOut.model_validate(booking)


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingOut,
    summary="Anulează rezervarea",
)
def cancel_booking(booking_id: int, user: CurrentUser, db: DbSession) -> BookingOut:
    return BookingOut.model_validate(BookingService(db).cancel(user, booking_id))
