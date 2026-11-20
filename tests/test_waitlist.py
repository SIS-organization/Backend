"""Epic 7 – lista de așteptare: KAN-44 (înscriere / ieșire), KAN-45 (ofertă),
KAN-46 (acceptare și refuz cu mutare)."""

from datetime import datetime

from sqlalchemy import func, select

from app.models import (
    BlockedSlot,
    BlockReason,
    Booking,
    BookingStatus,
    Notification,
    NotificationCategory,
)
from tests.conftest import (
    ADMIN,
    ANDREI,
    BAZIN,
    DARIA,
    ELENA,
    TEREN,
    VLAD,
    headers,
    make_booking,
    slot,
)

URL = "/v1/waitlist"
TOMORROW_10 = datetime(2030, 1, 8, 10)


def join(client, user=DARIA, facility=TEREN, replace=None, **slot_args):
    body = {"facilityId": facility, **slot(**slot_args)}
    if replace is not None:
        body["replaceBookingId"] = replace
    return client.post(URL, json=body, headers=headers(user))


def entry(client, entry_id, user=DARIA):
    return client.get(f"{URL}/{entry_id}", headers=headers(user)).json()


def cancel(client, booking_id, user=ANDREI):
    return client.post(f"/v1/bookings/{booking_id}/cancel", headers=headers(user))


def accept(client, entry_id, user=DARIA):
    return client.post(f"{URL}/{entry_id}/accept", headers=headers(user))


def decline(client, entry_id, user=DARIA):
    return client.post(f"{URL}/{entry_id}/decline", headers=headers(user))


def set_now(monkeypatch, now):
    for module in ("booking_service", "waitlist_service", "waitlist_offers"):
        monkeypatch.setattr(f"app.services.{module}.now_local", lambda: now)


def confirmed_count(db, user_id):
    db.expire_all()
    return db.scalar(
        select(func.count()).where(
            Booking.user_id == user_id, Booking.status == BookingStatus.CONFIRMED
        )
    )


# ======================= KAN-44: înscriere și ieșire =======================
def test_join_a_booked_slot(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    response = join(client)
    assert response.status_code == 201
    body = response.json()
    assert response.headers["Location"] == f"/v1/waitlist/{body['id']}"
    assert body["status"] == "active"
    assert body["position"] == 1
    assert body["facility"] == {"id": TEREN, "name": "Teren"}
    assert body["user"]["id"] == DARIA
    assert body["startTime"] == "2030-01-08T10:00:00+02:00"
    assert body["offerExpiresAt"] is None and body["replaceBookingId"] is None


def test_positions_follow_the_order_of_joining(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    assert join(client, user=DARIA).json()["position"] == 1
    assert join(client, user=ELENA).json()["position"] == 2


def test_free_slot_cannot_be_waitlisted(client):
    response = join(client)
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_IS_FREE_BOOK_DIRECTLY"


def test_blocked_slot_cannot_be_waitlisted(client, db):
    for reason in (BlockReason.UNIVERSITY_COURSE, BlockReason.MAINTENANCE):
        db.query(BlockedSlot).delete()
        db.add(
            BlockedSlot(
                facility_id=TEREN,
                created_by_user_id=ADMIN,
                start_time=TOMORROW_10,
                end_time=datetime(2030, 1, 8, 11),
                reason=reason,
            )
        )
        db.commit()
        response = join(client)
        assert response.status_code == 409
        assert response.json()["code"] == "WAITLIST_NOT_AVAILABLE_FOR_BLOCKED_SLOT"


def test_cannot_wait_for_a_slot_you_already_booked(client, db):
    make_booking(db, user_id=DARIA, start=TOMORROW_10)
    response = join(client, user=DARIA)
    assert response.status_code == 409
    assert response.json()["code"] == "USER_ALREADY_BOOKED"


def test_cannot_join_twice(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    assert join(client).status_code == 201
    response = join(client)
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_ON_WAITLIST"


def test_join_validates_the_slot(client, db):
    assert join(client, hour=22).status_code == 422  # după program
    response = join(client, day=6)  # în trecut
    assert response.status_code == 422
    assert response.json()["code"] == "SLOT_IN_THE_PAST"


def test_replace_booking_must_be_mine_and_active(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    andrei_other = make_booking(db, user_id=ANDREI, start=datetime(2030, 1, 9, 18))
    assert join(client, replace=andrei_other.id).status_code == 404
    cancelled = make_booking(
        db,
        user_id=DARIA,
        start=datetime(2030, 1, 9, 18),
        status=BookingStatus.CANCELLED,
    )
    response = join(client, replace=cancelled.id)
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_BOOKING_STATE"


def test_leave_the_waitlist(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    first = join(client, user=DARIA).json()
    second = join(client, user=ELENA).json()
    response = client.delete(f"{URL}/{first['id']}", headers=headers(DARIA))
    assert response.status_code == 204
    assert entry(client, first["id"])["status"] == "cancelled"
    assert entry(client, first["id"])["position"] is None
    # cel din spate urcă pe primul loc
    assert entry(client, second["id"], user=ELENA)["position"] == 1
    # după ieșire se poate înscrie din nou
    assert join(client, user=DARIA).status_code == 201


def test_waitlist_entries_are_private(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    mine = join(client, user=DARIA).json()
    assert client.get(f"{URL}/{mine['id']}", headers=headers(VLAD)).status_code == 403
    assert (
        client.delete(f"{URL}/{mine['id']}", headers=headers(VLAD)).status_code == 403
    )
    assert client.get(f"{URL}/{mine['id']}", headers=headers(ADMIN)).status_code == 200
    assert client.get(f"{URL}/999", headers=headers(DARIA)).status_code == 404


def test_list_my_waitlist(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    make_booking(db, user_id=ANDREI, start=datetime(2030, 1, 9, 10))
    join(client, user=DARIA)
    join(client, user=DARIA, day=9)
    join(client, user=ELENA)
    mine = client.get(URL, headers=headers(DARIA)).json()
    assert [e["startTime"][:13] for e in mine] == ["2030-01-08T10", "2030-01-09T10"]
    active = client.get(URL, params={"status": "offered"}, headers=headers(DARIA))
    assert active.json() == []


def test_availability_shows_the_waitlist(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    join(client, user=DARIA)
    join(client, user=ELENA)
    days = client.get(
        f"/v1/facilities/{TEREN}/availability",
        params={"from": "2030-01-08", "to": "2030-01-08"},
        headers=headers(VLAD),
    ).json()["days"]
    cell = next(
        s for s in days[0]["slots"] if s["startTime"].startswith("2030-01-08T10")
    )
    assert cell["waitlistAvailable"] is True and cell["waitlistCount"] == 2


# ======================= KAN-45: oferta la eliberare =======================
def test_cancel_offers_the_slot_to_the_first_in_line(client, db):
    booking = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    first = join(client, user=DARIA).json()
    second = join(client, user=ELENA).json()

    response = cancel(client, booking.id)
    assert response.json()["waitlistNotified"] == 1

    offered = entry(client, first["id"])
    assert offered["status"] == "offered"
    assert offered["offerExpiresAt"] == "2030-01-07T09:30:00+02:00"  # acum + 30 min
    assert entry(client, second["id"], user=ELENA)["status"] == "active"


def test_offer_arrives_as_a_notification(client, db):
    booking = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    first = join(client, user=DARIA).json()
    cancel(client, booking.id)

    notes = db.scalars(select(Notification)).all()
    assert len(notes) == 1
    note = notes[0]
    assert note.user_id == DARIA
    assert note.category is NotificationCategory.WAITLIST_OFFER
    assert note.waitlist_entry_id == first["id"]
    assert "08.01.2030, 10:00–11:00" in note.body and "Teren" in note.title


def test_cancel_without_waitlist_notifies_nobody(client, db):
    booking = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    assert cancel(client, booking.id).json()["waitlistNotified"] == 0


def test_reschedule_offers_the_old_slot(client, db):
    booking = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    waiting = join(client, user=DARIA).json()
    response = client.patch(
        f"/v1/bookings/{booking.id}", json=slot(day=9, hour=15), headers=headers(ANDREI)
    )
    assert response.status_code == 200
    assert entry(client, waiting["id"])["status"] == "offered"


def test_expired_offer_passes_to_the_next(client, db, monkeypatch):
    booking = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    first = join(client, user=DARIA).json()
    second = join(client, user=ELENA).json()
    cancel(client, booking.id)

    set_now(monkeypatch, datetime(2030, 1, 7, 9, 31))  # după expirarea ofertei
    response = accept(client, first["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "OFFER_EXPIRED"
    assert entry(client, second["id"], user=ELENA)["status"] == "offered"


# ======================= KAN-46: acceptare și refuz =======================
def test_accept_moves_the_booking_and_keeps_the_quota(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    mine = make_booking(db, user_id=DARIA, start=datetime(2030, 1, 8, 18))
    waiting = join(client, user=DARIA, replace=mine.id).json()
    assert waiting["replaceBookingId"] == mine.id
    cancel(client, taken.id)
    before = confirmed_count(db, DARIA)

    response = accept(client, waiting["id"])
    assert response.status_code == 200
    moved = response.json()
    assert moved["status"] == "confirmed"
    assert moved["startTime"] == "2030-01-08T10:00:00+02:00"
    assert moved["replacedBookingId"] == mine.id

    old = client.get(f"/v1/bookings/{mine.id}", headers=headers(DARIA)).json()
    assert old["status"] == "cancelled"
    # mutarea ÎNLOCUIEȘTE rezervarea: tot atâtea rezervări active (cota neschimbată)
    assert confirmed_count(db, DARIA) == before == 1
    assert entry(client, waiting["id"])["status"] == "fulfilled"


def test_accept_without_replace_creates_a_booking(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    waiting = join(client, user=DARIA).json()
    cancel(client, taken.id)
    response = accept(client, waiting["id"])
    assert response.status_code == 200
    assert response.json()["replacedBookingId"] is None
    assert confirmed_count(db, DARIA) == 1


def test_accept_offers_the_old_slot_to_its_own_waitlist(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    mine = make_booking(db, user_id=DARIA, start=datetime(2030, 1, 8, 18))
    waiting = join(client, user=DARIA, replace=mine.id).json()
    for_18 = join(client, user=ELENA, hour=18).json()
    cancel(client, taken.id)

    assert accept(client, waiting["id"]).status_code == 200
    assert entry(client, for_18["id"], user=ELENA)["status"] == "offered"


def test_accept_when_slot_was_taken_meanwhile(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    mine = make_booking(db, user_id=DARIA, start=datetime(2030, 1, 8, 18))
    waiting = join(client, user=DARIA, replace=mine.id).json()
    cancel(client, taken.id)
    make_booking(db, user_id=VLAD, start=TOMORROW_10)  # cineva a rezervat direct

    response = accept(client, waiting["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_NO_LONGER_AVAILABLE"
    old = client.get(f"/v1/bookings/{mine.id}", headers=headers(DARIA)).json()
    assert old["status"] == "confirmed"  # rezervarea veche rămâne activă
    again = entry(client, waiting["id"])
    assert again["status"] == "active" and again["position"] == 1


def test_accept_without_an_offer(client, db):
    make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    waiting = join(client, user=DARIA).json()
    response = accept(client, waiting["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "NO_ACTIVE_OFFER"


def test_only_the_owner_answers_the_offer(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    waiting = join(client, user=DARIA).json()
    cancel(client, taken.id)
    assert accept(client, waiting["id"], user=ELENA).status_code == 403
    assert decline(client, waiting["id"], user=ADMIN).status_code == 403
    assert accept(client, 999).status_code == 404


def test_decline_keeps_my_booking_and_passes_the_offer(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    mine = make_booking(db, user_id=DARIA, start=datetime(2030, 1, 8, 18))
    first = join(client, user=DARIA, replace=mine.id).json()
    second = join(client, user=ELENA).json()
    cancel(client, taken.id)

    response = decline(client, first["id"])
    assert response.status_code == 204
    assert entry(client, first["id"])["status"] == "declined"
    assert entry(client, second["id"], user=ELENA)["status"] == "offered"
    kept = client.get(f"/v1/bookings/{mine.id}", headers=headers(DARIA)).json()
    assert kept["status"] == "confirmed"
    # a doua oară nu mai există ofertă
    assert decline(client, first["id"]).json()["code"] == "NO_ACTIVE_OFFER"


def test_leaving_with_an_offer_passes_it_on(client, db):
    taken = make_booking(db, user_id=ANDREI, start=TOMORROW_10)
    first = join(client, user=DARIA).json()
    second = join(client, user=ELENA).json()
    cancel(client, taken.id)
    client.delete(f"{URL}/{first['id']}", headers=headers(DARIA))
    assert entry(client, second["id"], user=ELENA)["status"] == "offered"


def test_capacity_offers_one_spot_per_freed_place(client, db):
    bookings = [
        make_booking(db, user_id=u, facility_id=BAZIN, start=TOMORROW_10)
        for u in (ANDREI, ELENA, VLAD, ADMIN)
    ]
    first = join(client, user=DARIA, facility=BAZIN).json()
    cancel(client, bookings[0].id)
    assert entry(client, first["id"])["status"] == "offered"
    # al doilea loc eliberat nu are pe nimeni care să aștepte
    assert cancel(client, bookings[1].id, user=ELENA).json()["waitlistNotified"] == 0
