from datetime import datetime

from app.models import BlockedSlot, BlockReason, Facility
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


def create(client, user=ANDREI, facility=TEREN, **slot_args):
    body = {"facilityId": facility, **slot(**slot_args)}
    return client.post("/v1/bookings", json=body, headers=headers(user))


def test_create_booking_returns_201_and_contract(client):
    response = create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["facility"] == {"id": TEREN, "name": "Teren", "location": "Campus USV"}
    assert body["user"] == {"id": ANDREI, "firstName": "Andrei", "lastName": "Munteanu"}
    assert body["startTime"] == "2030-01-08T10:00:00+02:00"
    assert body["endTime"] == "2030-01-08T11:00:00+02:00"
    assert body["durationMinutes"] == 60
    assert body["status"] == "confirmed"
    assert body["earlyReleasedAt"] is None
    assert body["createdAt"].endswith("+02:00")
    assert "lane" not in body and "code" not in body


def test_utc_input_is_converted_to_local_time(client):
    body = {
        "facilityId": TEREN,
        "startTime": "2030-01-08T08:00:00Z",
        "endTime": "2030-01-08T09:00:00Z",
    }
    response = client.post("/v1/bookings", json=body, headers=headers(ANDREI))
    assert response.status_code == 201
    assert response.json()["startTime"] == "2030-01-08T10:00:00+02:00"


def test_requires_user_header(client):
    body = {"facilityId": TEREN, **slot()}
    response = client.post("/v1/bookings", json=body)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_unknown_user_is_401(client):
    response = create(client, user=999)
    assert response.status_code == 401


def test_invalid_body_is_400_validation_error(client):
    response = client.post(
        "/v1/bookings", json={"facilityId": "abc"}, headers=headers(ANDREI)
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    fields = {e["field"] for e in body["errors"]}
    assert {"facilityId", "startTime", "endTime"} <= fields


def test_unknown_facility_is_404(client):
    response = create(client, facility=999)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_end_before_start_is_invalid_range(client):
    body = {
        "facilityId": TEREN,
        "startTime": "2030-01-08T11:00:00+02:00",
        "endTime": "2030-01-08T10:00:00+02:00",
    }
    response = client.post("/v1/bookings", json=body, headers=headers(ANDREI))
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TIME_RANGE"


def test_duration_must_be_one_hour(client):
    body = {
        "facilityId": TEREN,
        "startTime": "2030-01-08T10:00:00+02:00",
        "endTime": "2030-01-08T12:00:00+02:00",
    }
    response = client.post("/v1/bookings", json=body, headers=headers(ANDREI))
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TIME_RANGE"


def test_start_must_be_on_the_hour(client):
    body = {
        "facilityId": TEREN,
        "startTime": "2030-01-08T10:30:00+02:00",
        "endTime": "2030-01-08T11:30:00+02:00",
    }
    response = client.post("/v1/bookings", json=body, headers=headers(ANDREI))
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_TIME_RANGE"


def test_outside_opening_hours(client):
    early = create(client, hour=7)
    late = create(client, hour=21)
    assert early.status_code == late.status_code == 422
    assert early.json()["code"] == "OUTSIDE_OPENING_HOURS"
    assert late.json()["code"] == "OUTSIDE_OPENING_HOURS"


def test_first_and_last_slot_of_the_day_are_allowed(client):
    assert create(client, hour=8).status_code == 201
    assert create(client, hour=20).status_code == 201


def test_slot_in_the_past(client):
    response = create(client, day=7, hour=8)  # azi, înainte de "acum" (09:00)
    assert response.status_code == 422
    assert response.json()["code"] == "SLOT_IN_THE_PAST"


def test_same_slot_twice_is_conflict(client):
    assert create(client, user=ANDREI).status_code == 201
    response = create(client, user=DARIA)
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_ALREADY_BOOKED"


def test_cancelled_booking_frees_the_slot(client, db):
    make_booking(db, user_id=ANDREI, start=datetime(2030, 1, 8, 10))
    client.post("/v1/bookings/1/cancel", headers=headers(ANDREI))
    assert create(client, user=DARIA).status_code == 201


def test_same_user_cannot_book_same_facility_twice_in_slot(client):
    assert create(client, user=ANDREI, facility=BAZIN).status_code == 201
    response = create(client, user=ANDREI, facility=BAZIN)
    assert response.status_code == 409
    assert response.json()["code"] == "USER_ALREADY_BOOKED"


def test_pool_allows_four_simultaneous_bookings_but_not_five(client):
    for user in (ANDREI, DARIA, ELENA, ADMIN):
        assert create(client, user=user, facility=BAZIN).status_code == 201
    response = create(client, user=VLAD, facility=BAZIN)
    assert response.status_code == 409
    assert response.json()["code"] == "SLOT_ALREADY_BOOKED"


def test_different_slot_is_independent(client):
    assert create(client, hour=10).status_code == 201
    assert create(client, hour=11, user=DARIA).status_code == 201


def test_inactive_facility_is_maintenance_conflict(client, db):
    facility = db.get(Facility, TEREN)
    facility.is_active = False
    db.commit()
    response = create(client)
    assert response.status_code == 409
    assert response.json()["code"] == "FACILITY_UNDER_MAINTENANCE"


def test_blocked_for_maintenance(client, db):
    db.add(
        BlockedSlot(
            facility_id=TEREN,
            created_by_user_id=ADMIN,
            start_time=datetime(2030, 1, 8, 9),
            end_time=datetime(2030, 1, 8, 12),
            reason=BlockReason.MAINTENANCE,
        )
    )
    db.commit()
    response = create(client, hour=10)
    assert response.status_code == 409
    assert response.json()["code"] == "FACILITY_UNDER_MAINTENANCE"


def test_blocked_by_university_course(client, db):
    db.add(
        BlockedSlot(
            facility_id=TEREN,
            created_by_user_id=ADMIN,
            start_time=datetime(2030, 1, 8, 10),
            end_time=datetime(2030, 1, 8, 12),
            reason=BlockReason.UNIVERSITY_COURSE,
        )
    )
    db.commit()
    response = create(client, hour=11)
    assert response.status_code == 409
    assert response.json()["code"] == "BLOCKED_BY_UNIVERSITY_ACTIVITY"
    # Un interval vecin, care nu se suprapune, rămâne liber.
    assert create(client, hour=12).status_code == 201
