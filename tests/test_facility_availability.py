from datetime import datetime

from app.models import BlockedSlot, BlockReason, BookingStatus, Facility
from tests.conftest import (
    ADMIN,
    ANDREI,
    BAZIN,
    DARIA,
    ELENA,
    TEREN,
    headers,
    make_booking,
)

URL = "/v1/facilities/{}/availability"


def get(client, facility=TEREN, user=ANDREI, **params):
    return client.get(URL.format(facility), params=params, headers=headers(user))


def by_slot(response):
    """{(data, ora): slot} pentru acces ușor în teste."""
    return {
        (day["date"], int(slot["startTime"][11:13])): slot
        for day in response.json()["days"]
        for slot in day["slots"]
    }


def test_default_range_is_seven_days_from_today(client):
    response = get(client)
    assert response.status_code == 200
    body = response.json()
    assert len(body["days"]) == 7
    assert body["from"] == "2030-01-07" and body["to"] == "2030-01-13"
    first = body["days"][0]
    assert first["date"] == "2030-01-07" and first["isToday"] is True
    assert body["days"][1]["isToday"] is False
    assert len(first["slots"]) == 13  # 08:00–20:00 = 13 intervale pe zi
    assert (first["open"], first["close"]) == ("08:00", "21:00")


def test_availability_json_shape(client):
    body = get(client, **{"from": "2030-01-08", "to": "2030-01-08"}).json()
    assert body["facilityId"] == TEREN
    assert body["timezone"] == "Europe/Bucharest"
    assert body["generatedAt"].endswith("+02:00")
    slot = by_slot(get(client, **{"from": "2030-01-08", "to": "2030-01-08"}))[
        ("2030-01-08", 10)
    ]
    assert slot == {
        "startTime": "2030-01-08T10:00:00+02:00",
        "endTime": "2030-01-08T11:00:00+02:00",
        "status": "free",
        "label": None,
        "bookable": True,
        "bookedByMe": False,
        "waitlistAvailable": False,
        "waitlistCount": 0,
        "capacity": 1,
        "freeSpots": 1,
    }


def test_past_slots_are_marked_past(client):
    slots = by_slot(get(client))  # acum = luni 09:00
    assert slots[("2030-01-07", 8)]["status"] == "past"
    assert slots[("2030-01-07", 8)]["bookable"] is False
    assert slots[("2030-01-07", 9)]["status"] == "free"  # începe chiar acum


def test_booked_slot(client, db):
    make_booking(db, user_id=ANDREI, facility_id=TEREN, start=datetime(2030, 1, 8, 10))
    slots = by_slot(get(client, user=DARIA))
    assert slots[("2030-01-08", 10)]["status"] == "booked"
    assert slots[("2030-01-08", 10)]["freeSpots"] == 0
    assert slots[("2030-01-08", 10)]["bookable"] is False
    assert slots[("2030-01-08", 11)]["status"] == "free"


def test_booked_by_me_is_only_true_for_the_owner(client, db):
    make_booking(db, user_id=ANDREI, facility_id=TEREN, start=datetime(2030, 1, 8, 10))
    mine = by_slot(get(client, user=ANDREI))[("2030-01-08", 10)]
    other = by_slot(get(client, user=DARIA))[("2030-01-08", 10)]
    assert mine["bookedByMe"] is True
    assert other["bookedByMe"] is False


def test_cancelled_booking_leaves_slot_free(client, db):
    make_booking(db, start=datetime(2030, 1, 8, 10), status=BookingStatus.CANCELLED)
    assert by_slot(get(client))[("2030-01-08", 10)]["status"] == "free"


def test_pool_shows_free_lanes(client, db):
    for user in (ANDREI, DARIA, ELENA):
        make_booking(
            db, user_id=user, facility_id=BAZIN, start=datetime(2030, 1, 8, 10)
        )
    slot = by_slot(get(client, BAZIN))[("2030-01-08", 10)]
    assert (slot["status"], slot["capacity"], slot["freeSpots"]) == ("free", 4, 1)

    make_booking(db, user_id=ADMIN, facility_id=BAZIN, start=datetime(2030, 1, 8, 10))
    slot = by_slot(get(client, BAZIN))[("2030-01-08", 10)]
    assert (slot["status"], slot["freeSpots"]) == ("booked", 0)


def test_bookings_of_other_facilities_do_not_count(client, db):
    make_booking(db, facility_id=BAZIN, start=datetime(2030, 1, 8, 10))
    assert by_slot(get(client, TEREN))[("2030-01-08", 10)]["status"] == "free"


def _block(db, reason, start_hour=10, end_hour=12):
    db.add(
        BlockedSlot(
            facility_id=TEREN,
            created_by_user_id=ADMIN,
            start_time=datetime(2030, 1, 8, start_hour),
            end_time=datetime(2030, 1, 8, end_hour),
            reason=reason,
        )
    )
    db.commit()


def test_university_course_status_and_label(client, db):
    _block(db, BlockReason.UNIVERSITY_COURSE)
    slots = by_slot(get(client))
    assert slots[("2030-01-08", 10)]["status"] == "university_course"
    assert slots[("2030-01-08", 10)]["label"] == "Curs USV"
    assert slots[("2030-01-08", 10)]["bookable"] is False
    assert slots[("2030-01-08", 11)]["status"] == "university_course"
    assert slots[("2030-01-08", 12)]["status"] == "free"
    assert slots[("2030-01-08", 9)]["status"] == "free"


def test_university_event_status(client, db):
    _block(db, BlockReason.UNIVERSITY_EVENT)
    slot = by_slot(get(client))[("2030-01-08", 10)]
    assert (slot["status"], slot["label"]) == ("university_event", "Eveniment USV")


def test_maintenance_block(client, db):
    _block(db, BlockReason.MAINTENANCE, 8, 9)
    slot = by_slot(get(client))[("2030-01-08", 8)]
    assert (slot["status"], slot["label"]) == ("maintenance", "Mentenanță")


def test_inactive_facility_is_closed(client, db):
    facility = db.get(Facility, TEREN)
    facility.is_active = False
    db.commit()
    slots = by_slot(get(client))
    assert slots[("2030-01-08", 10)]["status"] == "closed"
    assert slots[("2030-01-07", 8)]["status"] == "past"


def test_custom_range(client):
    days = get(client, **{"from": "2030-01-10", "to": "2030-01-11"}).json()["days"]
    assert [d["date"] for d in days] == ["2030-01-10", "2030-01-11"]


def test_to_before_from_is_400(client):
    response = get(client, **{"from": "2030-01-11", "to": "2030-01-10"})
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_range_too_long_is_400(client):
    response = get(client, **{"from": "2030-01-01", "to": "2030-01-16"})  # 16 zile
    assert response.status_code == 400
    assert get(client, **{"from": "2030-01-01", "to": "2030-01-14"}).status_code == 200


def test_bad_date_is_400(client):
    response = get(client, **{"from": "azi"})
    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "from"


def test_unknown_facility_is_404(client):
    assert get(client, 999).status_code == 404


def test_requires_authentication(client):
    response = client.get(URL.format(TEREN))
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
