from datetime import datetime

from app.models import BookingStatus
from tests.conftest import ANDREI, DARIA, headers, make_booking, slot


def patch(client, booking_id, user=ANDREI, **slot_args):
    return client.patch(
        f"/v1/bookings/{booking_id}", json=slot(**slot_args), headers=headers(user)
    )


# ---------- reschedule (PATCH) ----------
def test_reschedule_moves_booking(client, db):
    booking = make_booking(db, start=datetime(2030, 1, 8, 10))
    response = patch(client, booking.id, day=9, hour=15)
    assert response.status_code == 200
    body = response.json()
    assert body["startTime"] == "2030-01-09T15:00:00+02:00"
    assert body["endTime"] == "2030-01-09T16:00:00+02:00"


def test_reschedule_to_same_slot_is_allowed(client, db):
    booking = make_booking(db, start=datetime(2030, 1, 8, 10))
    assert patch(client, booking.id, day=8, hour=10).status_code == 200


def test_reschedule_to_taken_slot_is_conflict(client, db):
    make_booking(db, user_id=DARIA, start=datetime(2030, 1, 9, 15))
    mine = make_booking(db, user_id=ANDREI, start=datetime(2030, 1, 8, 10))
    response = patch(client, mine.id, day=9, hour=15)
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_ALREADY_BOOKED"


def test_reschedule_validates_new_slot(client, db):
    booking = make_booking(db)
    response = patch(client, booking.id, day=9, hour=22)
    assert response.status_code == 422


def test_reschedule_too_late(client, db):
    # începe în 1 oră (acum = 09:00) → sub limita de 2 ore
    booking = make_booking(db, start=datetime(2030, 1, 7, 10))
    response = patch(client, booking.id, day=9, hour=10)
    assert response.status_code == 422
    assert response.json()["code"] == "MODIFICATION_WINDOW_EXPIRED"


def test_cannot_reschedule_someone_elses_booking(client, db):
    booking = make_booking(db, user_id=ANDREI)
    assert patch(client, booking.id, user=DARIA, day=9).status_code == 403


def test_cannot_reschedule_cancelled_booking(client, db):
    booking = make_booking(db, status=BookingStatus.CANCELLED)
    response = patch(client, booking.id, day=9)
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_BOOKING_STATE"


def test_reschedule_missing_booking_is_404(client):
    assert patch(client, 999).status_code == 404


# ---------- cancel ----------
def test_cancel_sets_status_cancelled(client, db):
    booking = make_booking(db, start=datetime(2030, 1, 8, 10))
    response = client.post(f"/v1/bookings/{booking.id}/cancel", headers=headers(ANDREI))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    # rămâne în istoric (soft delete)
    history = client.get("/v1/bookings?scope=history", headers=headers(ANDREI)).json()
    assert history["totalItems"] == 1


def test_cancel_exactly_two_hours_before_is_allowed(client, db):
    booking = make_booking(db, start=datetime(2030, 1, 7, 11))  # acum 09:00
    response = client.post(f"/v1/bookings/{booking.id}/cancel", headers=headers(ANDREI))
    assert response.status_code == 200


def test_cancel_less_than_two_hours_before_is_rejected(client, db):
    booking = make_booking(db, start=datetime(2030, 1, 7, 10))
    response = client.post(f"/v1/bookings/{booking.id}/cancel", headers=headers(ANDREI))
    assert response.status_code == 422
    assert response.json()["code"] == "CANCELLATION_WINDOW_EXPIRED"


def test_cancel_twice_is_conflict(client, db):
    booking = make_booking(db)
    url = f"/v1/bookings/{booking.id}/cancel"
    assert client.post(url, headers=headers(ANDREI)).status_code == 200
    response = client.post(url, headers=headers(ANDREI))
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_BOOKING_STATE"


def test_cannot_cancel_someone_elses_booking(client, db):
    booking = make_booking(db, user_id=ANDREI)
    response = client.post(f"/v1/bookings/{booking.id}/cancel", headers=headers(DARIA))
    assert response.status_code == 403


def test_cancel_missing_booking_is_404(client):
    assert (
        client.post("/v1/bookings/999/cancel", headers=headers(ANDREI)).status_code
        == 404
    )
