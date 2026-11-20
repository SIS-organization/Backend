"""KAN-45: oferta către lista de așteptare când se eliberează un interval.

Folosit de anulare, de mutarea unei rezervări și de răspunsurile la ofertă.
Nu face commit: rulează în tranzacția celui care l-a apelat, deci oferta și
eliberarea locului se salvează împreună (sau deloc).
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import now_local
from app.models import (
    Notification,
    NotificationCategory,
    WaitlistEntry,
    WaitlistStatus,
)
from app.repositories.blocked_slot_repository import BlockedSlotRepository
from app.repositories.booking_repository import BookingRepository
from app.repositories.facility_repository import FacilityRepository
from app.repositories.waitlist_repository import WaitlistRepository


class WaitlistOffers:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.entries = WaitlistRepository(db)
        self.bookings = BookingRepository(db)
        self.facilities = FacilityRepository(db)
        self.blocked_slots = BlockedSlotRepository(db)
        self.settings = get_settings()

    def offer_freed_slot(self, facility_id: int, start: datetime, end: datetime) -> int:
        """Trimite oferta următorilor din listă, câte unul pentru fiecare loc liber.

        Un loc pentru care o ofertă așteaptă răspuns nu mai este oferit altcuiva.
        Returnează câți utilizatori au fost notificați.
        """
        self.db.flush()  # sesiunea nu face autoflush: numărăm starea curentă
        now = now_local()
        facility = self.facilities.get_for_update(facility_id)
        if facility is None or not facility.is_active or start <= now:
            return 0
        # Intervalele blocate (curs, eveniment, mentenanță) nu se oferă.
        if self.blocked_slots.find_overlapping(facility_id, start, end) is not None:
            return 0

        free = (
            facility.capacity
            - self.bookings.count_overlapping(facility_id, start, end)
            - self.entries.count_offered(facility_id, start)
        )
        notified = 0
        while free > 0:
            entry = self.entries.next_active(facility_id, start)
            if entry is None:
                break
            self._offer(entry, facility.name, now)
            free -= 1
            notified += 1
        return notified

    def expire_due(self) -> None:
        """Închide ofertele la care nu s-a răspuns la timp și dă locul mai departe.

        Intrările al căror interval a început deja expiră și ele.
        """
        now = now_local()
        freed: set[tuple[int, datetime, datetime]] = set()
        for entry in self.entries.list_due(now):
            was_offered = entry.status == WaitlistStatus.OFFERED
            entry.status = WaitlistStatus.EXPIRED
            if was_offered and entry.start_time > now:
                freed.add((entry.facility_id, entry.start_time, entry.end_time))
        for facility_id, start, end in sorted(freed):
            self.offer_freed_slot(facility_id, start, end)
        self.db.flush()

    def pass_on(self, entry: WaitlistEntry) -> int:
        """Locul oferit acestei intrări trece la următorul din listă."""
        return self.offer_freed_slot(
            entry.facility_id, entry.start_time, entry.end_time
        )

    def _offer(self, entry: WaitlistEntry, facility_name: str, now: datetime) -> None:
        ttl = timedelta(minutes=self.settings.waitlist_offer_ttl_minutes)
        entry.status = WaitlistStatus.OFFERED
        entry.offered_at = now
        entry.offer_expires_at = min(now + ttl, entry.start_time)

        interval = f"{entry.start_time:%d.%m.%Y, %H:%M}–{entry.end_time:%H:%M}"
        if entry.replace_booking_id is not None:
            body = (
                f"S-a eliberat intervalul {interval} la {facility_name}. "
                "Dacă accepți, rezervarea ta actuală este mutată (înlocuită, "
                "nu se adaugă una nouă)."
            )
        else:
            body = f"S-a eliberat intervalul {interval} la {facility_name}."
        body += f" Răspunde până la {entry.offer_expires_at:%H:%M}."
        self.db.add(
            Notification(
                user_id=entry.user_id,
                category=NotificationCategory.WAITLIST_OFFER,
                title=f"S-a eliberat un loc la {facility_name}",
                body=body,
                booking_id=entry.replace_booking_id,
                waitlist_entry_id=entry.id,
            )
        )
        self.db.flush()
