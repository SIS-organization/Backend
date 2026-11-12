from tests.conftest import headers


def test_health_ok(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["database"] == "up"


def test_list_facilities(client):
    response = client.get("/v1/facilities")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [f["name"] for f in items] == [
        "Teren",
        "Sală fitness",
        "Bazin",
        "Sală de sport",
    ]
    pool = items[2]
    assert pool["type"] == "swimming_pool"
    assert pool["capacity"] == 4
    assert pool["isActive"] is True


def test_unknown_route_is_problem_json(client):
    response = client.get("/v1/nu-exista", headers=headers(1))
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "NOT_FOUND"
