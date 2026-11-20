"""Lista de așteptare (Epic 7).

* KAN-44: înscriere și ieșire, doar pentru intervale ocupate de rezervări;
* KAN-45: oferta la eliberarea unui interval (vezi `waitlist_offers.py`);
* KAN-46: acceptarea ofertei (mutare care înlocuiește rezervarea) și refuzul ei.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.time import now_local, to_local_naive
from app.models import (
    Booking,
    BookingStatus,
    CancellationSource,
    User,
    UserRole,
    WaitlistEntry,
    WaitlistStatus,
)
from app.repositories.booking_repository import BookingRepository
from app.repositories.waitlist_repository import OPEN_STATUSES, WaitlistRepository
from app.schemas.waitlist import WaitlistEntryOut, WaitlistFacility, WaitlistUser
from app.services.booking_service import BookingService
from app.services.waitlist_offers import WaitlistOffers

# Erorile de disponibilitate care, la acceptare, înseamnă „locul nu mai e liber".
_SLOT_TAKEN_CODES = {
    "SLOT_ALREADY_BOOKED",
    "FACILITY_UNDER_MAINTENANCE",
    "SLOT_BLOCKED_BY_UNIVERSITY_ACTIVITY",
}


class WaitlistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.entries = WaitlistRepository(db)
        self.bookings = BookingRepository(db)
        self.booking_rules = BookingService(db)
        self.offers = WaitlistOffers(db)

    # ---------- KAN-44: înscriere ----------
    def join(
        self,
        user: User,
        facility_id: int,
        start_time: datetime,
        end_time: datetime,
        replace_booking_id: int | None = None,
    ) -> WaitlistEntry:
        start, end = to_local_naive(start_time), to_local_naive(end_time)
        self.booking_rules._validate_slot(start, end)
        self._ensure_slot_is_waitlistable(user, facility_id, start, end)

        if self.entries.find_open(user.id, facility_id, start) is not None:
            raise ConflictError(
                "Ești deja pe lista de așteptare pentru acest interval.",
                code="ALREADY_ON_WAITLIST",
            )
        if replace_booking_id is not None:
            self._ensure_replaceable(user, replace_booking_id)

        entry = self.entries.add(
            WaitlistEntry(
                user_id=user.id,
                facility_id=facility_id,
                start_time=start,
                end_time=end,
                replace_booking_id=replace_booking_id,
            )
        )
        self.db.commit()
        return self._reload(entry.id)

    def _ensure_slot_is_waitlistable(
        self, user: User, facility_id: int, start: datetime, end: datetime
    ) -> None:
        """Lista de așteptare există doar pentru un interval ocupat de rezervări."""
        try:
            self.booking_rules._ensure_slot_available(user.id, facility_id, start, end)
        except ConflictError as error:
            if error.code == "SLOT_ALREADY_BOOKED":
                return  # ocupat de rezervări: aici are sens lista de așteptare
            if error.code in (
                "FACILITY_UNDER_MAINTENANCE",
                "SLOT_BLOCKED_BY_UNIVERSITY_ACTIVITY",
            ):
                raise ConflictError(
                    "Intervalul este blocat (curs, eveniment sau mentenanță), "
                    "deci nu are listă de așteptare.",
                    code="WAITLIST_NOT_AVAILABLE_FOR_BLOCKED_SLOT",
                ) from error
            raise  # ex. USER_ALREADY_BOOKED: ai deja acest interval
        raise ConflictError(
            "Intervalul este liber: îl poți rezerva direct.",
            code="SLOT_IS_FREE_BOOK_DIRECTLY",
        )

    def _ensure_replaceable(self, user: User, booking_id: int) -> Booking:
        """Rezervarea de mutat trebuie să fie a utilizatorului și încă activă."""
        booking = self.bookings.get(booking_id)
        if booking is None or booking.user_id != user.id:
            raise NotFoundError(f"Rezervarea {booking_id} nu există.")
        if booking.status != BookingStatus.CONFIRMED or booking.end_time <= now_local():
            raise ConflictError(
                "Rezervarea de mutat nu mai este activă.",
                code="INVALID_BOOKING_STATE",
            )
        return booking

    # ---------- citire ----------
    def list_for_user(
        self, user: User, status: WaitlistStatus | None = None
    ) -> list[WaitlistEntry]:
        self._expire_due()
        return self.entries.list_for_user(user.id, status)

    def get(self, user: User, entry_id: int) -> WaitlistEntry:
        self._expire_due()
        return self._get_visible(user, entry_id)

    def present(self, entry: WaitlistEntry) -> WaitlistEntryOut:
        is_open = entry.status in OPEN_STATUSES
        return WaitlistEntryOut(
            id=entry.id,
            facility=WaitlistFacility(id=entry.facility.id, name=entry.facility.name),
            user=WaitlistUser(
                id=entry.user.id,
                name=f"{entry.user.first_name} {entry.user.last_name}",
            ),
            start_time=entry.start_time,
            end_time=entry.end_time,
            position=self.entries.position(entry) if is_open else None,
            status=entry.status,
            replace_booking_id=entry.replace_booking_id,
            offer_expires_at=(
                entry.offer_expires_at
                if entry.status == WaitlistStatus.OFFERED
                else None
            ),
            created_at=entry.created_at,
        )

    # ---------- KAN-44: ieșire ----------
    def leave(self, user: User, entry_id: int) -> None:
        """Ieșirea de pe listă. Dacă avea o ofertă, locul trece la următorul."""
        self._expire_due()
        entry = self._get_visible(user, entry_id)
        if entry.status in OPEN_STATUSES:
            had_offer = entry.status == WaitlistStatus.OFFERED
            entry.status = WaitlistStatus.CANCELLED
            if had_offer:
                self.offers.pass_on(entry)
        self.db.commit()

    # ---------- KAN-46: acceptare ----------
    def accept(self, user: User, entry_id: int) -> Booking:
        """Acceptă oferta: noua rezervare o înlocuiește pe cea veche (dacă există).

        Intervalul este reverificat. Dacă nu mai este liber, rezervarea veche
        rămâne activă, iar utilizatorul rămâne pe listă (409 SLOT_NO_LONGER_AVAILABLE).
        """
        self._expire_due()
        entry = self._get_own_offer(user, entry_id)

        old: Booking | None = None
        if entry.replace_booking_id is not None:
            old = self._ensure_replaceable(user, entry.replace_booking_id)

        try:
            self.booking_rules._validate_slot(entry.start_time, entry.end_time)
            self.booking_rules._ensure_slot_available(
                user.id,
                entry.facility_id,
                entry.start_time,
                entry.end_time,
                exclude_id=old.id if old else None,
            )
        except ConflictError as error:
            if error.code not in _SLOT_TAKEN_CODES:
                raise
            # Rămâne pe listă, pe același loc, pentru următoarea eliberare.
            entry.status = WaitlistStatus.ACTIVE
            entry.offered_at = entry.offer_expires_at = None
            self.db.commit()
            raise ConflictError(
                "Intervalul nu mai este disponibil. Rezervarea ta rămâne neschimbată.",
                code="SLOT_NO_LONGER_AVAILABLE",
            ) from error

        booking = self.bookings.add(
            Booking(
                user_id=user.id,
                facility_id=entry.facility_id,
                start_time=entry.start_time,
                end_time=entry.end_time,
                replaced_booking_id=old.id if old else None,
            )
        )
        entry.status = WaitlistStatus.FULFILLED

        if old is not None:
            # Mutarea ÎNLOCUIEȘTE rezervarea veche: nu se adaugă una în plus,
            # deci cota lunară rămâne aceeași.
            old.status = BookingStatus.CANCELLED
            old.cancelled_by = CancellationSource.USER
            old.cancel_reason = (
                f"Mutată pe {entry.start_time:%d.%m.%Y %H:%M} (lista de așteptare)."
            )
            # Celelalte cereri de mutare ale aceleiași rezervări nu mai au sens.
            for other in self.entries.list_open_replacing(old.id, exclude_id=entry.id):
                had_offer = other.status == WaitlistStatus.OFFERED
                other.status = WaitlistStatus.CANCELLED
                if had_offer:
                    self.offers.pass_on(other)
            # Intervalul vechi s-a eliberat: îl primește lista lui de așteptare.
            self.offers.offer_freed_slot(old.facility_id, old.start_time, old.end_time)

        self.db.commit()
        return self.booking_rules._reload(booking.id)

    # ---------- KAN-46: refuz ----------
    def decline(self, user: User, entry_id: int) -> None:
        """Refuză oferta („Păstrez ora"): locul trece la următorul din listă."""
        self._expire_due()
        entry = self._get_own_offer(user, entry_id)
        entry.status = WaitlistStatus.DECLINED
        self.offers.pass_on(entry)
        self.db.commit()

    # ---------- reguli ----------
    def _expire_due(self) -> None:
        """Ofertele expirate se închid înainte de orice citire sau răspuns."""
        self.offers.expire_due()
        self.db.commit()

    def _get_visible(self, user: User, entry_id: int) -> WaitlistEntry:
        entry = self.entries.get(entry_id)
        if entry is None:
            raise NotFoundError(f"Intrarea {entry_id} nu există.")
        if entry.user_id != user.id and user.role != UserRole.ADMINISTRATOR:
            raise ForbiddenError("Nu ai acces la această intrare.")
        return entry

    def _get_own_offer(self, user: User, entry_id: int) -> WaitlistEntry:
        """Doar titularul răspunde la ofertă, și doar cât timp oferta e valabilă."""
        entry = self.entries.get(entry_id)
        if entry is None:
            raise NotFoundError(f"Intrarea {entry_id} nu există.")
        if entry.user_id != user.id:
            raise ForbiddenError("Nu ai acces la această intrare.")
        if entry.status == WaitlistStatus.EXPIRED:
            raise ConflictError("Oferta a expirat.", code="OFFER_EXPIRED")
        if entry.status != WaitlistStatus.OFFERED:
            raise ConflictError(
                "Nu există o ofertă activă pentru această intrare.",
                code="NO_ACTIVE_OFFER",
            )
        return entry

    def _reload(self, entry_id: int) -> WaitlistEntry:
        self.db.expire_all()
        entry = self.entries.get(entry_id)
        assert entry is not None
        return entry
