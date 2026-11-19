import pytest
from sqlalchemy import text

from tests.conftest import ADMIN, ANDREI, VLAD, headers


@pytest.fixture
def restore_users(db):
    """PATCH schimbă datele din seed: le punem la loc după test."""
    snapshot = db.execute(
        text("SELECT id, first_name, last_name FROM users")
    ).fetchall()
    yield
    db.rollback()
    for user_id, first_name, last_name in snapshot:
        db.execute(
            text("UPDATE users SET first_name = :f, last_name = :l WHERE id = :i"),
            {"f": first_name, "l": last_name, "i": user_id},
        )
    db.commit()


# ---------- GET /users/me ----------


def test_get_me_returns_current_user(client):
    response = client.get("/v1/users/me", headers=headers(ANDREI))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == ANDREI
    assert body["name"] == "Andrei Munteanu"
    assert body["firstName"] == "Andrei"
    assert body["lastName"] == "Munteanu"
    assert body["role"] == "student"
    assert body["identitySource"] == "sso"
    assert body["priority"] is True
    assert body["accessStatus"] == "active"
    assert "@" in body["email"]
    assert body["createdAt"]


def test_get_me_returns_the_right_user_and_role(client):
    admin = client.get("/v1/users/me", headers=headers(ADMIN)).json()
    external = client.get("/v1/users/me", headers=headers(VLAD)).json()
    assert admin["id"] == ADMIN and admin["role"] == "administrator"
    assert external["id"] == VLAD and external["role"] == "external"
    # publicul extern nu are acces prioritar și nu vine din SSO
    assert external["priority"] is False
    assert external["identitySource"] == "external_email"


def test_get_me_does_not_expose_sensitive_fields(client):
    body = client.get("/v1/users/me", headers=headers(ANDREI)).json()
    assert set(body) == {
        "id",
        "name",
        "email",
        "role",
        "identitySource",
        "priority",
        "accessStatus",
        "firstName",
        "lastName",
        "createdAt",
    }


def test_get_me_without_token_is_401(client):
    response = client.get("/v1/users/me")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_get_me_with_token_of_unknown_user_is_401(client):
    response = client.get("/v1/users/me", headers=headers(999))
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


# ---------- PATCH /users/me ----------


def test_patch_me_updates_names(client, restore_users):
    response = client.patch(
        "/v1/users/me",
        json={"firstName": "Alex", "lastName": "Popescu"},
        headers=headers(ANDREI),
    )
    assert response.status_code == 200
    assert response.json()["firstName"] == "Alex"
    assert response.json()["lastName"] == "Popescu"
    assert response.json()["name"] == "Alex Popescu"

    # schimbarea rămâne salvată
    again = client.get("/v1/users/me", headers=headers(ANDREI)).json()
    assert (again["firstName"], again["lastName"]) == ("Alex", "Popescu")


def test_patch_me_updates_only_sent_fields(client, restore_users):
    response = client.patch(
        "/v1/users/me", json={"firstName": "Alex"}, headers=headers(ANDREI)
    )
    assert response.status_code == 200
    assert response.json()["firstName"] == "Alex"
    assert response.json()["lastName"] == "Munteanu"


def test_patch_me_trims_whitespace(client, restore_users):
    response = client.patch(
        "/v1/users/me", json={"firstName": "  Alex  "}, headers=headers(ANDREI)
    )
    assert response.json()["firstName"] == "Alex"


def test_patch_me_does_not_change_other_users(client, restore_users):
    client.patch("/v1/users/me", json={"firstName": "Alex"}, headers=headers(ANDREI))
    other = client.get("/v1/users/me", headers=headers(ADMIN)).json()
    assert other["firstName"] != "Alex"


def test_patch_me_cannot_change_role_or_email(client, restore_users):
    response = client.patch(
        "/v1/users/me",
        json={"firstName": "Alex", "role": "administrator", "email": "x@y.ro"},
        headers=headers(ANDREI),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "student"
    assert body["email"] != "x@y.ro"


@pytest.mark.parametrize(
    "payload",
    [{}, {"firstName": ""}, {"firstName": "   "}, {"lastName": "x" * 51}],
)
def test_patch_me_with_invalid_body_is_400(client, payload):
    response = client.patch("/v1/users/me", json=payload, headers=headers(ANDREI))
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_patch_me_without_token_is_401(client):
    response = client.patch("/v1/users/me", json={"firstName": "Alex"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
