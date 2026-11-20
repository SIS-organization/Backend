from datetime import datetime

from app.models import BlockedSlot, BlockReason, Facility
from tests.conftest import (
    ADMIN,
    ANDREI,
    BAZIN,
    FITNESS,
    SALA,
    TEREN,
    headers,
    make_booking,
)


def facilities(client, **params):
    return client.get("/v1/facilities", params=params, headers=headers(ANDREI))


def names(response):
    return [f["name"] for f in response.json()["items"]]


def test_health_ok(client):
    response = client.get("/v1/health")  # public, fără antet
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["database"] == "ok"


def test_list_facilities_shape(client):
    response = facilities(client)
    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["pageSize"]) == (1, 20)
    assert (body["totalItems"], body["totalPages"]) == (4, 1)
    assert names(response) == ["Teren", "Sală fitness", "Bazin", "Sală de sport"]

    pool = body["items"][2]
    assert pool["id"] == BAZIN
    assert pool["campus"] == "Campus USV"
    assert pool["sports"] == [{"code": "swimming", "label": "Înot"}]
    assert {"code": "swim_lanes", "label": "Culoare de înot"} in pool["amenities"]
    assert pool["status"] == "operational"
    assert pool["statusNote"] is None
    assert (pool["openingTime"], pool["closingTime"]) == ("08:00", "21:00")
    assert pool["slotDurationMinutes"] == 60
    assert pool["timezone"] == "Europe/Bucharest"
    assert pool["type"] == "swimming_pool" and pool["capacity"] == 4


def test_next_free_slot_is_the_current_hour(client):
    # acum = luni 09:00; intervalul de la 09:00 începe chiar acum
    slot = facilities(client).json()["items"][0]["nextFreeSlot"]
    assert slot == {
        "startTime": "2030-01-07T09:00:00+02:00",
        "endTime": "2030-01-07T10:00:00+02:00",
    }


def test_next_free_slot_skips_booked_hours(client, db):
    make_booking(db, facility_id=TEREN, start=datetime(2030, 1, 7, 9))
    slot = facilities(client).json()["items"][0]["nextFreeSlot"]
    assert slot["startTime"] == "2030-01-07T10:00:00+02:00"


def test_next_free_slot_for_a_given_date(client):
    slot = facilities(client, date="2030-01-09").json()["items"][0]["nextFreeSlot"]
    assert slot["startTime"] == "2030-01-09T08:00:00+02:00"


def test_filter_by_sport(client):
    assert names(facilities(client, sport="swimming")) == ["Bazin"]
    assert names(facilities(client, sport="volleyball")) == ["Sală de sport"]


def test_filter_by_amenities_requires_all(client):
    assert names(facilities(client, amenities="showers")) == ["Sală fitness", "Bazin"]
    assert names(facilities(client, amenities="showers,swim_lanes")) == ["Bazin"]


def test_search_ignores_case_and_diacritics(client):
    assert names(facilities(client, q="BAZIN")) == ["Bazin"]
    assert names(facilities(client, q="inot")) == ["Bazin"]  # sportul „Înot"
    assert names(facilities(client, q="sala")) == ["Sală fitness", "Sală de sport"]
    assert names(facilities(client, q="nimic")) == []


def test_unknown_sport_or_amenity_is_400(client):
    assert facilities(client, sport="golf").status_code == 400
    response = facilities(client, amenities="jacuzzi")
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_pagination(client):
    page = facilities(client, pageSize=3, page=2).json()
    assert [f["name"] for f in page["items"]] == ["Sală de sport"]
    assert (page["totalItems"], page["totalPages"]) == (4, 2)


def test_facility_under_maintenance_status(client, db):
    db.add(
        BlockedSlot(
            facility_id=SALA,
            created_by_user_id=ADMIN,
            start_time=datetime(2030, 1, 7, 8),
            end_time=datetime(2030, 1, 7, 12),
            reason=BlockReason.MAINTENANCE,
        )
    )
    db.commit()
    hall = facilities(client).json()["items"][3]
    assert hall["status"] == "under_maintenance"
    assert hall["statusNote"] == "Astăzi 08:00–12:00"
    assert names(facilities(client, includeUnavailable="false")) == [
        "Teren",
        "Sală fitness",
        "Bazin",
    ]


def test_university_activity_and_closed_status(client, db):
    db.add(
        BlockedSlot(
            facility_id=TEREN,
            created_by_user_id=ADMIN,
            start_time=datetime(2030, 1, 7, 8),
            end_time=datetime(2030, 1, 7, 12),
            reason=BlockReason.UNIVERSITY_COURSE,
        )
    )
    db.get(Facility, FITNESS).is_active = False
    db.commit()
    items = facilities(client).json()["items"]
    assert items[0]["status"] == "university_activity"
    assert items[1]["status"] == "closed"
    assert items[1]["nextFreeSlot"] is None


def test_facilities_require_authentication(client):
    response = client.get("/v1/facilities")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_unknown_route_is_problem_json(client):
    response = client.get("/v1/nu-exista", headers=headers(1))
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "NOT_FOUND"
