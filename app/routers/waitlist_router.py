"""Endpoint-uri pentru lista de așteptare (Epic 7: KAN-44, KAN-46)."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.models import WaitlistStatus
from app.routers.dependencies import CurrentUser, DbSession
from app.schemas.booking import BookingOut
from app.schemas.waitlist import WaitlistCreate, WaitlistEntryOut
from app.services.waitlist_service import WaitlistService

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


@router.get(
    "",
    response_model=list[WaitlistEntryOut],
    summary="Intrările mele pe lista de așteptare",
)
def list_my_waitlist(
    user: CurrentUser,
    db: DbSession,
    entry_status: Annotated[WaitlistStatus | None, Query(alias="status")] = None,
) -> list[WaitlistEntryOut]:
    service = WaitlistService(db)
    return [service.present(e) for e in service.list_for_user(user, entry_status)]


@router.post(
    "",
    response_model=WaitlistEntryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Intră pe lista de așteptare",
    description=(
        "Doar pentru un interval **ocupat de rezervări** (nu pentru intervale libere "
        "sau blocate). Cu `replaceBookingId`, acceptarea ofertei **mută** rezervarea "
        "indicată (o înlocuiește, nu adaugă una nouă)."
    ),
)
def join_waitlist(
    body: WaitlistCreate, response: Response, user: CurrentUser, db: DbSession
) -> WaitlistEntryOut:
    service = WaitlistService(db)
    entry = service.join(
        user, body.facility_id, body.start_time, body.end_time, body.replace_booking_id
    )
    response.headers["Location"] = f"/v1/waitlist/{entry.id}"
    return service.present(entry)


@router.get(
    "/{entry_id}",
    response_model=WaitlistEntryOut,
    summary="Detaliile unei intrări pe lista de așteptare",
)
def get_waitlist_entry(
    entry_id: int, user: CurrentUser, db: DbSession
) -> WaitlistEntryOut:
    service = WaitlistService(db)
    return service.present(service.get(user, entry_id))


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Renunță la lista de așteptare",
)
def leave_waitlist(entry_id: int, user: CurrentUser, db: DbSession) -> Response:
    WaitlistService(db).leave(user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{entry_id}/accept",
    response_model=BookingOut,
    summary="Acceptă oferta (solicită mutarea / rezervarea)",
    description=(
        "Reverifică intervalul. Dacă e liber, se creează rezervarea nouă, iar cea "
        "veche (`replaceBookingId`) este anulată: cota rămâne neschimbată. Altfel "
        "`409 SLOT_NO_LONGER_AVAILABLE` și rezervarea veche rămâne activă."
    ),
)
def accept_waitlist_offer(
    entry_id: int, user: CurrentUser, db: DbSession
) -> BookingOut:
    service = WaitlistService(db)
    return service.booking_rules.present(service.accept(user, entry_id))


@router.post(
    "/{entry_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Refuză oferta („Păstrez ora")',
)
def decline_waitlist_offer(entry_id: int, user: CurrentUser, db: DbSession) -> Response:
    WaitlistService(db).decline(user, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
