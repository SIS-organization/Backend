"""Două persoane nu pot lua ultimul loc liber în același timp."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import ADMIN, ANDREI, BAZIN, DARIA, ELENA, VLAD, headers, slot


def test_five_simultaneous_requests_for_four_lanes(client):
    def book(user_id: int) -> int:
        with TestClient(app) as local_client:
            body = {"facilityId": BAZIN, **slot()}
            return local_client.post(
                "/v1/bookings", json=body, headers=headers(user_id)
            ).status_code

    users = [ANDREI, DARIA, ELENA, ADMIN, VLAD]
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = sorted(pool.map(book, users))

    assert statuses == [201, 201, 201, 201, 409]
