"""KAN-19: autentificarea cu SSO (furnizor simulat) și emiterea JWT-ului."""

from datetime import timedelta
from urllib.parse import parse_qsl, urlsplit

import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import (
    SSO_STATE,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    encode_token,
)
from app.models import UserRole
from app.services.sso import SsoIdentity, build_sso_provider, role_for_identity
from app.services.sso.pkce import challenge_for, verifier_for
from tests.conftest import ADMIN, ANDREI, DARIA, ELENA

ANDREI_EMAIL = "andrei.munteanu@student.usv.ro"
LOGIN = "/v1/auth/sso/login"
CALLBACK = "/v1/auth/sso/callback"
AUTHORIZE = "/v1/auth/sso/mock/authorize"


@pytest.fixture(autouse=True)
def restore_users(db):
    """Testele modifică utilizatorii; după fiecare test refacem datele de seed."""
    rows = db.execute(
        text("SELECT id, email, first_name, last_name, role, password_hash FROM users")
    ).all()
    seed_ids = [row.id for row in rows]
    yield
    db.rollback()
    db.execute(text("DELETE FROM users WHERE id <> ALL(:ids)"), {"ids": seed_ids})
    for row in rows:
        db.execute(
            text(
                "UPDATE users SET email=:email, first_name=:first, last_name=:last,"
                " role=:role, password_hash=:pw WHERE id=:id"
            ),
            {
                "id": row.id,
                "email": row.email,
                "first": row.first_name,
                "last": row.last_name,
                "role": row.role,
                "pw": row.password_hash,
            },
        )
    db.commit()


def start(client, redirect_to=None):
    params = {"redirectTo": redirect_to} if redirect_to else {}
    response = client.get(LOGIN, params=params, follow_redirects=False)
    assert response.status_code == 302, response.text
    return response


def idp_query(login_response) -> dict:
    return dict(parse_qsl(urlsplit(login_response.headers["location"]).query))


def authorize(client, query: dict, email: str):
    return client.get(
        AUTHORIZE, params={**query, "login_hint": email}, follow_redirects=False
    )


def callback_params(authorize_response) -> dict:
    assert authorize_response.status_code == 302, authorize_response.text
    return dict(parse_qsl(urlsplit(authorize_response.headers["location"]).query))


def sign_in(client, email, redirect_to=None):
    """Tot fluxul: login -> SSO simulat -> callback. Întoarce răspunsul final."""
    query = idp_query(start(client, redirect_to))
    return client.get(CALLBACK, params=callback_params(authorize(client, query, email)))


def user_row(db, email):
    return db.execute(
        text(
            "SELECT id, role, first_name, last_name, password_hash FROM users"
            " WHERE email = :e"
        ),
        {"e": email},
    ).first()


# ---------- /auth/sso/login ----------
def test_login_redirects_to_sso_with_state_and_pkce(client):
    response = start(client)
    location = urlsplit(response.headers["location"])
    assert location.path == AUTHORIZE
    query = idp_query(response)
    assert query["response_type"] == "code"
    assert query["code_challenge_method"] == "S256"
    assert len(query["code_challenge"]) == 43
    assert query["state"]
    assert query["redirect_uri"].endswith("/v1/auth/sso/callback")


def test_login_works_without_authentication(client):
    assert client.get(LOGIN, follow_redirects=False).status_code == 302


@pytest.mark.parametrize(
    "redirect_to",
    [
        "https://evil.example",
        "//evil.example",
        "/\\evil",
        "javascript:alert(1)",
        "facilitati",
        "/a b",
        "/" + "x" * 300,
    ],
)
def test_login_rejects_unsafe_redirect_to(client, redirect_to):
    response = client.get(LOGIN, params={"redirectTo": redirect_to})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_REDIRECT"


def test_each_login_gets_a_different_state_and_challenge(client):
    first, second = idp_query(start(client)), idp_query(start(client))
    assert first["state"] != second["state"]
    assert first["code_challenge"] != second["code_challenge"]


# ---------- fluxul complet: rol corect + JWT (criteriul „Gata când”) ----------
def test_student_gets_correct_role_and_a_jwt(client):
    response = sign_in(client, ANDREI_EMAIL)
    assert response.status_code == 200
    body = response.json()

    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] == 3600
    assert body["user"]["id"] == ANDREI
    assert body["user"]["role"] == "student"
    assert body["user"]["email"] == ANDREI_EMAIL
    assert body["user"]["identitySource"] == "sso"
    assert body["user"]["priority"] is True

    claims = decode_access_token(body["accessToken"])
    assert claims["sub"] == str(ANDREI)
    assert claims["role"] == "student"
    assert claims["exp"] - claims["iat"] == 3600
    # token-ul de reînnoire nu poate fi folosit ca token de acces
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(body["refreshToken"])


def test_professor_gets_professor_role(client):
    body = sign_in(client, "elena.rusu@usv.ro").json()
    assert body["user"]["id"] == ELENA
    assert body["user"]["role"] == "professor"
    assert decode_access_token(body["accessToken"])["role"] == "professor"


def test_administrator_keeps_administrator_role(client):
    body = sign_in(client, "admin@usv.ro").json()
    assert body["user"]["id"] == ADMIN
    assert body["user"]["role"] == "administrator"
    assert decode_access_token(body["accessToken"])["role"] == "administrator"


def test_email_is_matched_case_insensitively(client):
    query = idp_query(start(client))
    params = callback_params(authorize(client, query, ANDREI_EMAIL.upper()))
    assert client.get(CALLBACK, params=params).json()["user"]["id"] == ANDREI


def test_response_is_not_cacheable(client):
    response = sign_in(client, ANDREI_EMAIL)
    assert response.headers["cache-control"] == "no-store"


def test_redirect_to_is_returned_to_the_frontend(client):
    assert (
        sign_in(client, ANDREI_EMAIL, "/rezervari").json()["redirectTo"] == "/rezervari"
    )
    assert sign_in(client, ANDREI_EMAIL).json()["redirectTo"] is None


# ---------- contul local ----------
def test_new_student_account_is_created_once(client, db):
    email = "ioana.popescu@student.usv.ro"
    assert user_row(db, email) is None

    first = sign_in(client, email).json()
    assert first["user"]["role"] == "student"
    assert first["user"]["name"] == "Ioana Popescu"
    created = user_row(db, email)
    assert created.password_hash == "!sso-fara-parola"  # fără parolă locală

    second = sign_in(client, email).json()
    assert second["user"]["id"] == first["user"]["id"]
    count = db.execute(
        text("SELECT count(*) FROM users WHERE email = :e"), {"e": email}
    ).scalar()
    assert count == 1


def test_names_are_refreshed_from_sso(client, db):
    db.execute(
        text("UPDATE users SET first_name = 'Gresit' WHERE email = :e"),
        {"e": ANDREI_EMAIL},
    )
    db.commit()
    assert sign_in(client, ANDREI_EMAIL).json()["user"]["firstName"] == "Andrei"


def test_role_follows_the_institution(client, db):
    db.execute(text("UPDATE users SET role = 'professor' WHERE id = :i"), {"i": DARIA})
    db.commit()  # în baza locală Daria apare cadru didactic, dar SSO spune student
    body = sign_in(client, "daria.stan@student.usv.ro").json()
    assert body["user"]["role"] == "student"
    assert user_row(db, "daria.stan@student.usv.ro").role == "student"


def test_existing_external_account_is_a_conflict(client, db):
    db.execute(text("UPDATE users SET role = 'external' WHERE id = :i"), {"i": ELENA})
    db.commit()
    response = sign_in(client, "elena.rusu@usv.ro")
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_CONFLICT"


# ---------- conturi neeligibile ----------
def test_disabled_account_is_forbidden(client, db):
    response = sign_in(client, "cont.dezactivat@student.usv.ro")
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DISABLED"
    assert user_row(db, "cont.dezactivat@student.usv.ro") is None


def test_non_institutional_account_is_forbidden(client, db):
    response = sign_in(client, "vizitator@example.com")
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "ACCOUNT_NOT_ELIGIBLE"
    assert response.headers["content-type"].startswith("application/problem+json")
    assert user_row(db, "vizitator@example.com") is None


# ---------- callback: cereri invalide ----------
@pytest.mark.parametrize(
    "params", [{}, {"code": "x"}, {"state": "x"}, {"code": "", "state": "x"}]
)
def test_callback_requires_code_and_state(client, params):
    response = client.get(CALLBACK, params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_callback_rejects_tampered_state(client):
    query = idp_query(start(client))
    params = callback_params(authorize(client, query, ANDREI_EMAIL))
    params["state"] = params["state"][:-3] + "abc"
    response = client.get(CALLBACK, params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_SSO_STATE"


def test_callback_rejects_expired_state(client):
    query = idp_query(start(client))
    params = callback_params(authorize(client, query, ANDREI_EMAIL))
    params["state"] = encode_token(SSO_STATE, {"nonce": "x"}, timedelta(seconds=-5))
    response = client.get(CALLBACK, params=params)
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_SSO_STATE"


def test_callback_rejects_a_forged_code(client):
    params = callback_params(authorize(client, idp_query(start(client)), ANDREI_EMAIL))
    params["code"] = "nu-este-un-cod-valid"
    response = client.get(CALLBACK, params=params)
    assert response.status_code == 401
    assert response.json()["code"] == "SSO_AUTHENTICATION_FAILED"


def test_callback_rejects_an_access_token_used_as_code(client):
    params = callback_params(authorize(client, idp_query(start(client)), ANDREI_EMAIL))
    params["code"] = create_access_token(ANDREI, UserRole.ADMINISTRATOR)
    assert client.get(CALLBACK, params=params).status_code == 401


def test_pkce_code_from_another_login_is_rejected(client):
    """Un cod furat dintr-o autentificare nu merge cu state-ul altei autentificări."""
    query_a = idp_query(start(client))
    query_b = idp_query(start(client))
    code_a = callback_params(authorize(client, query_a, ANDREI_EMAIL))["code"]
    response = client.get(CALLBACK, params={"code": code_a, "state": query_b["state"]})
    assert response.status_code == 401
    assert response.json()["code"] == "SSO_AUTHENTICATION_FAILED"


# ---------- furnizorul simulat (validări de tip furnizor real) ----------
def test_mock_idp_shows_account_picker_without_login_hint(client):
    query = idp_query(start(client))
    response = client.get(AUTHORIZE, params=query)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "login_hint=" in response.text
    assert ANDREI_EMAIL in response.text


@pytest.mark.parametrize(
    "override",
    [
        {"redirect_uri": "https://evil.example/cb"},
        {"code_challenge_method": "plain"},
        {"code_challenge": "scurt"},
        {"response_type": "token"},
    ],
)
def test_mock_idp_rejects_invalid_requests(client, override):
    query = {**idp_query(start(client)), **override}
    response = client.get(AUTHORIZE, params={**query, "login_hint": ANDREI_EMAIL})
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_SSO_REQUEST"


def test_mock_idp_rejects_unknown_account(client):
    query = idp_query(start(client))
    response = authorize(client, query, "necunoscut@usv.ro")
    assert response.status_code == 401


def test_mock_endpoints_are_hidden_from_swagger(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/auth/sso/login" in paths
    assert "/v1/auth/sso/callback" in paths
    assert not any("mock" in path for path in paths)


# ---------- rolul din identitate ----------
@pytest.mark.parametrize(
    ("email", "affiliations", "expected"),
    [
        ("a@student.usv.ro", (), UserRole.STUDENT),
        ("a@usv.ro", (), UserRole.PROFESSOR),
        ("A@STUDENT.USV.RO", (), UserRole.STUDENT),
        ("x@gmail.com", ("student",), UserRole.STUDENT),
        ("x@gmail.com", ("faculty",), UserRole.PROFESSOR),
        ("x@gmail.com", ("Employee",), UserRole.PROFESSOR),
        ("x@student.usv.ro", ("student", "faculty"), UserRole.PROFESSOR),
        ("x@student.usv.ro", ("faculty",), UserRole.PROFESSOR),
        ("x@gmail.com", (), None),
        ("x@usv.ro.evil.com", (), None),
        ("x@evil-usv.ro", (), None),
        ("x@gmail.com", ("member",), None),
    ],
)
def test_role_for_identity(email, affiliations, expected):
    assert role_for_identity(SsoIdentity(email, "A", "B", affiliations)) == expected


def test_administrator_is_never_assigned_from_identity():
    for affiliations in (("admin",), ("administrator",), ("staff", "faculty")):
        identity = SsoIdentity("admin@usv.ro", "A", "B", affiliations)
        assert role_for_identity(identity) != UserRole.ADMINISTRATOR


# ---------- JWT și PKCE ----------
def test_access_token_claims_follow_swagger():
    claims = decode_access_token(create_access_token(7, UserRole.PROFESSOR))
    assert claims["sub"] == "7" and claims["role"] == "professor"
    assert {"exp", "iat", "token_use"} <= claims.keys()


def test_tokens_of_other_types_are_not_access_tokens():
    state = encode_token(SSO_STATE, {"nonce": "n"}, timedelta(minutes=1))
    for token in (state, create_refresh_token(1)):
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(token)


def test_tampered_or_unsigned_tokens_are_rejected():
    token = create_access_token(1, UserRole.STUDENT)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token[:-2] + "xx")
    unsigned = jwt.encode(
        {"sub": "1", "role": "administrator"}, key=None, algorithm="none"
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(unsigned)


def test_expired_access_token_is_rejected():
    from app.core.security import ACCESS

    expired = encode_token(
        ACCESS, {"sub": "1", "role": "student"}, timedelta(seconds=-1)
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_pkce_verifier_and_challenge():
    verifier = verifier_for("nonce-1")
    assert 43 <= len(verifier) <= 128
    assert verifier == verifier_for("nonce-1") != verifier_for("nonce-2")
    # vector din RFC 7636, anexa B
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert challenge_for(rfc_verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


# ---------- configurare ----------
def test_jwt_secret_must_be_long_enough():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, database_url="postgresql+psycopg://x/y", jwt_secret="scurt"
        )


def test_real_sso_mode_is_not_configured_yet():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://x/y",
        jwt_secret="x" * 40,
        sso_mode="oidc",
    )
    with pytest.raises(AppError) as error:
        build_sso_provider(settings, mock_authorize_url=None)
    assert error.value.status_code == 501
    assert error.value.code == "SSO_NOT_CONFIGURED"
