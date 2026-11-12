from datetime import datetime

from app.models import BookingStatus
from tests.conftest import ADMIN, ANDREI, DARIA, TEREN, headers, make_booking


def test_get_own_booking(client, db):
    booking = make_booking(db)
    response = client.get(f"/v1/bookings/{booking.id}", headers=headers(ANDREI))
    assert response.status_code == 200
    assert response.json()["id"] == booking.id


def test_get_missing_booking_is_404(client):
    response = client.get("/v1/bookings/999", headers=headers(ANDREI))
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_cannot_get_someone_elses_booking(client, db):
    booking = make_booking(db, user_id=ANDREI)
    response = client.get(f"/v1/bookings/{booking.id}", headers=headers(DARIA))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


def test_administrator_can_get_any_booking(client, db):
    booking = make_booking(db, user_id=ANDREI)
    response = client.get(f"/v1/bookings/{booking.id}", headers=headers(ADMIN))
    assert response.status_code == 200


def _seed_three(db):
    make_booking(db, start=datetime(2030, 1, 9, 10))  # viitor
    make_booking(db, start=datetime(2030, 1, 8, 10))  # viitor, mai devreme
    make_booking(db, start=datetime(2030, 1, 3, 10))  # trecut
    make_booking(
        db, start=datetime(2030, 1, 10, 10), status=BookingStatus.CANCELLED
    )  # anulată
    make_booking(db, user_id=DARIA, start=datetime(2030, 1, 8, 12))  # a altcuiva


def test_list_upcoming_is_default_sorted_ascending(client, db):
    _seed_three(db)
    response = client.get("/v1/bookings", headers=headers(ANDREI))
    body = response.json()
    assert response.status_code == 200
    assert body["totalItems"] == 2
    starts = [b["startTime"] for b in body["items"]]
    assert starts == ["2030-01-08T10:00:00+02:00", "2030-01-09T10:00:00+02:00"]


def test_list_history_has_past_and_cancelled_newest_first(client, db):
    _seed_three(db)
    response = client.get("/v1/bookings?scope=history", headers=headers(ANDREI))
    body = response.json()
    assert body["totalItems"] == 2
    assert [b["status"] for b in body["items"]] == ["cancelled", "confirmed"]


def test_list_all(client, db):
    _seed_three(db)
    response = client.get("/v1/bookings?scope=all", headers=headers(ANDREI))
    assert response.json()["totalItems"] == 4


def test_pagination(client, db):
    for day in range(8, 13):
        make_booking(db, start=datetime(2030, 1, day, 10))
    response = client.get("/v1/bookings?page=2&pageSize=2", headers=headers(ANDREI))
    body = response.json()
    assert body["page"] == 2
    assert body["pageSize"] == 2
    assert body["totalItems"] == 5
    assert body["totalPages"] == 3
    assert [b["startTime"][:10] for b in body["items"]] == ["2030-01-10", "2030-01-11"]


def test_invalid_pagination_is_400(client):
    response = client.get("/v1/bookings?pageSize=1000", headers=headers(ANDREI))
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_invalid_scope_is_400(client):
    response = client.get("/v1/bookings?scope=banana", headers=headers(ANDREI))
    assert response.status_code == 400


def test_empty_list(client):
    body = client.get("/v1/bookings", headers=headers(ANDREI)).json()
    assert body == {
        "items": [],
        "page": 1,
        "pageSize": 20,
        "totalItems": 0,
        "totalPages": 0,
    }


def test_facility_in_list_item(client, db):
    make_booking(db, facility_id=TEREN)
    item = client.get("/v1/bookings", headers=headers(ANDREI)).json()["items"][0]
    assert item["facility"]["name"] == "Teren"
