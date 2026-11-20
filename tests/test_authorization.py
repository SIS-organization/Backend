"""KAN-21: verificarea JWT și protejarea endpoint-urilor după rol."""

import re
from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest

from app.core.exceptions import ForbiddenError
from app.core.security import (
    ACCESS,
    SSO_STATE,
    create_access_token,
    create_refresh_token,
    derive_key,
    encode_token,
)
from app.main import app
from app.models import UserRole
from app.routers import admin_router
from app.routers.dependencies import require_admin, require_roles
from tests.conftest import ADMIN, ANDREI, DARIA, ELENA, VLAD, headers
from tests.test_sso import sign_in

# Singurele endpoint-uri publice. Un endpoint nou este protejat implicit: dacă
# trebuie să fie public, se adaugă DELIBERAT aici (și testele îl verifică).
PUBLIC = {
    ("GET", "/v1/health"),
    ("GET", "/v1/auth/sso/login"),
    ("GET", "/v1/auth/sso/callback"),
}

ME = "/v1/users/me"
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def operations() -> list[tuple[str, str]]:
    return [
        (method.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        for method in ops
    ]


def concrete(path: str) -> str:
    """/v1/bookings/{booking_id} -> /v1/bookings/1"""
    return re.sub(r"\{[^}]+\}", "1", path)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_unauthenticated(response):
    assert response.status_code == 401, response.text
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "UNAUTHENTICATED"
    assert body["title"] == "Unauthorized"
    assert body["status"] == 401


# ---------- „verificăm JWT-ul pe fiecare endpoint” ----------
@pytest.mark.parametrize(
    ("method", "path"), [op for op in operations() if op not in PUBLIC]
)
def test_every_non_public_endpoint_requires_authentication(client, method, path):
    assert_unauthenticated(client.request(method, concrete(path)))


@pytest.mark.parametrize(("method", "path"), operations())
def test_openapi_declares_security_exactly_on_non_public_endpoints(method, path):
    operation = app.openapi()["paths"][path][method.lower()]
    assert ("security" in operation) == ((method, path) not in PUBLIC)


def test_public_endpoints_work_without_authentication(client):
    assert client.get("/v1/health").status_code == 200
    assert client.get("/v1/auth/sso/login", follow_redirects=False).status_code == 302
    # callback fără parametri: 400 (cerere invalidă), nu 401
    assert client.get("/v1/auth/sso/callback").status_code == 400


def test_swagger_documents_the_bearer_scheme(client):
    scheme = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert scheme["bearerAuth"]["type"] == "http"
    assert scheme["bearerAuth"]["scheme"] == "bearer"
    assert scheme["bearerAuth"]["bearerFormat"] == "JWT"


# ---------- token-uri respinse (401) ----------
def _signed(claims: dict, key: bytes | None = None, algorithm: str = "HS256") -> str:
    return jwt.encode(claims, key or derive_key(ACCESS), algorithm=algorithm)


def _claims(**override) -> dict:
    now = 2_000_000_000
    base = {
        "sub": str(ANDREI),
        "role": "student",
        "token_use": ACCESS,
        "iat": now - 1000,
        "exp": now + 1000,
    }
    return {**base, **override}


def _bad_tokens() -> dict[str, str]:
    import time

    now = int(time.time())
    valid = {"iat": now - 10, "exp": now + 600}
    good = create_access_token(ANDREI, UserRole.STUDENT)
    return {
        "tampered": good[:-3] + "abc",
        "expired": encode_token(
            ACCESS, {"sub": "1", "role": "student"}, timedelta(seconds=-5)
        ),
        "wrong_key": _signed(_claims(**valid), key=b"alta-cheie" * 4),
        "alg_none": jwt.encode(_claims(**valid), key=None, algorithm="none"),
        "refresh_token": create_refresh_token(ANDREI),
        "sso_state_token": encode_token(
            SSO_STATE, {"nonce": "n"}, timedelta(minutes=5)
        ),
        "no_expiration": _signed(
            {k: v for k, v in _claims(**valid).items() if k != "exp"}
        ),
        "non_numeric_sub": _signed(_claims(**valid, sub="abc")),
        "negative_sub": _signed(_claims(**valid, sub="-1")),
        "unknown_user": _signed(_claims(**valid, sub="999")),
        "unknown_role": _signed(_claims(**valid, role="superadmin")),
        "missing_role": _signed(
            {k: v for k, v in _claims(**valid).items() if k != "role"}
        ),
        "garbage": "nu-este-un-jwt",
    }


@pytest.mark.parametrize("name", list(_bad_tokens()))
def test_invalid_tokens_are_rejected_with_401(client, name):
    assert_unauthenticated(client.get(ME, headers=bearer(_bad_tokens()[name])))


@pytest.mark.parametrize(
    "authorization", ["", "Bearer", "Bearer ", "Basic YWxleDpwYXJvbGE=", "token abc"]
)
def test_missing_or_wrong_scheme_is_401(client, authorization):
    assert_unauthenticated(client.get(ME, headers={"Authorization": authorization}))


def test_expired_token_says_so(client):
    token = _bad_tokens()["expired"]
    response = client.get(ME, headers=bearer(token))
    assert "expirat" in response.json()["detail"]


def test_old_x_user_id_header_no_longer_authenticates(client):
    assert_unauthenticated(client.get(ME, headers={"X-User-Id": str(ADMIN)}))
    assert_unauthenticated(client.get("/v1/admin/bookings", headers={"X-User-Id": "4"}))


# ---------- token valid ----------
@pytest.mark.parametrize(
    ("user_id", "role"),
    [
        (ANDREI, "student"),
        (ELENA, "professor"),
        (ADMIN, "administrator"),
        (VLAD, "external"),
    ],
)
def test_valid_token_identifies_the_user(client, user_id, role):
    body = client.get(ME, headers=headers(user_id)).json()
    assert body["id"] == user_id
    assert body["role"] == role


# ---------- /admin/*: 401 fără autentificare, 403 pentru ne-administratori ----------
ADMIN_PATHS = [
    "/v1/admin",
    "/v1/admin/",
    "/v1/admin/bookings",
    "/v1/admin/users/5/block",
    "/v1/admin/inexistent/adanc/imbricat",
]


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_admin_without_authentication_is_401(client, method, path):
    assert_unauthenticated(client.request(method, path))


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", ADMIN_PATHS)
@pytest.mark.parametrize("user_id", [ANDREI, DARIA, ELENA, VLAD])
def test_admin_for_non_administrators_is_403(client, method, path, user_id):
    response = client.request(method, path, headers=headers(user_id))
    assert response.status_code == 403, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "FORBIDDEN"
    assert body["title"] == "Forbidden"
    assert body["detail"] == "Nu ai permisiunea necesară."


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_administrator_passes_the_guard(client, method, path):
    """Garda lasă administratorul să treacă; nu există încă endpoint-uri admin."""
    response = client.request(method, path, headers=headers(ADMIN))
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.parametrize("name", ["tampered", "expired", "refresh_token"])
def test_admin_with_an_invalid_token_is_401_not_404(client, name):
    token = _bad_tokens()[name]
    assert_unauthenticated(client.get("/v1/admin/bookings", headers=bearer(token)))


def test_role_is_taken_from_the_database_not_from_the_token(client):
    """Un token care pretinde `administrator` nu dă drepturi unui student."""
    forged = create_access_token(ANDREI, UserRole.ADMINISTRATOR)
    assert client.get("/v1/admin/x", headers=bearer(forged)).status_code == 403
    # invers: administratorul rămâne administrator chiar dacă token-ul spune altceva
    stale = create_access_token(ADMIN, UserRole.STUDENT)
    assert client.get("/v1/admin/x", headers=bearer(stale)).status_code == 404


def test_other_endpoints_are_not_admin_only(client):
    """Regula `/admin/*` nu blochează restul API-ului pentru ne-administratori."""
    for user_id in (ANDREI, ELENA, VLAD):
        assert client.get(ME, headers=headers(user_id)).status_code == 200
        assert client.get("/v1/facilities", headers=headers(user_id)).status_code == 200


# ---------- garda este pe router, deci protejează și endpoint-urile viitoare ----------
def test_admin_routers_carry_the_guard():
    for router in (admin_router.router, admin_router.fallback_router):
        assert any(dep.dependency is require_admin for dep in router.dependencies)


@pytest.mark.parametrize(
    ("allowed", "role", "passes"),
    [
        ((UserRole.ADMINISTRATOR,), UserRole.ADMINISTRATOR, True),
        ((UserRole.ADMINISTRATOR,), UserRole.PROFESSOR, False),
        ((UserRole.PROFESSOR, UserRole.ADMINISTRATOR), UserRole.PROFESSOR, True),
        ((UserRole.PROFESSOR, UserRole.ADMINISTRATOR), UserRole.STUDENT, False),
        ((UserRole.STUDENT,), UserRole.EXTERNAL, False),
    ],
)
def test_require_roles(allowed, role, passes):
    guard = require_roles(*allowed)
    user = SimpleNamespace(role=role)
    if passes:
        assert guard(user) is user
    else:
        with pytest.raises(ForbiddenError) as error:
            guard(user)
        assert error.value.code == "FORBIDDEN"


def test_require_roles_needs_at_least_one_role():
    with pytest.raises(ValueError):
        require_roles()


# ---------- cap-coadă: SSO (KAN-19) + protecție (KAN-21) ----------
def test_token_from_sso_login_works_on_the_api(client):
    student = sign_in(client, "andrei.munteanu@student.usv.ro").json()
    me = client.get(ME, headers=bearer(student["accessToken"]))
    assert me.status_code == 200 and me.json()["role"] == "student"
    assert (
        client.get("/v1/admin/x", headers=bearer(student["accessToken"])).status_code
        == 403
    )

    admin = sign_in(client, "admin@usv.ro").json()
    assert (
        client.get("/v1/admin/x", headers=bearer(admin["accessToken"])).status_code
        == 404
    )
