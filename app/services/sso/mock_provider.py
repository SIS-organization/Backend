"""Furnizor SSO SIMULAT (dezvoltare și demo). NU se folosește în producție.

Simulează comportamentul unui furnizor OpenID Connect, cu același flux ca cel
real (state, PKCE S256, cod de autorizare cu valabilitate scurtă), ca să putem
testa tot lanțul fără acces la SSO-ul universității.

Furnizorul simulat este „stateless”: codul de autorizare este un token semnat
care conține identitatea și `code_challenge`-ul, deci funcționează corect și cu
mai multe procese ale serverului.
"""

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import SSO_CODE, decode_token, encode_token
from app.services.sso.pkce import challenge_for
from app.services.sso.provider import SsoIdentity

CODE_TTL = timedelta(seconds=60)


@dataclass(frozen=True)
class MockAccount:
    """Un cont din „directorul” universității simulat."""

    identity: SsoIdentity
    description: str


MOCK_ACCOUNTS: tuple[MockAccount, ...] = (
    MockAccount(
        SsoIdentity(
            "andrei.munteanu@student.usv.ro", "Andrei", "Munteanu", ("student",)
        ),
        "Student (există în baza de date)",
    ),
    MockAccount(
        SsoIdentity("daria.stan@student.usv.ro", "Daria", "Stan", ("student",)),
        "Student (există în baza de date)",
    ),
    MockAccount(
        SsoIdentity("ioana.popescu@student.usv.ro", "Ioana", "Popescu", ("student",)),
        "Student NOU (contul local se creează la prima autentificare)",
    ),
    MockAccount(
        SsoIdentity("elena.rusu@usv.ro", "Elena", "Rusu", ("faculty",)),
        "Cadru didactic",
    ),
    MockAccount(
        SsoIdentity("admin@usv.ro", "Administrator", "Baza Sportiva", ("staff",)),
        "Administrator (rolul vine din baza de date)",
    ),
    MockAccount(
        SsoIdentity(
            "cont.dezactivat@student.usv.ro", "Cont", "Dezactivat", ("student",), False
        ),
        "Cont dezactivat (primește 403)",
    ),
    MockAccount(
        SsoIdentity("vizitator@example.com", "Vizitator", "Extern"),
        "Fără afiliere USV (primește 403)",
    ),
)


def find_account(email: str) -> MockAccount | None:
    wanted = email.strip().lower()
    return next((a for a in MOCK_ACCOUNTS if a.identity.email == wanted), None)


def issue_code(account: MockAccount, *, code_challenge: str, redirect_uri: str) -> str:
    """Partea „furnizorului”: cod de autorizare după autentificarea contului."""
    ident = account.identity
    claims = {
        "email": ident.email,
        "given_name": ident.first_name,
        "family_name": ident.last_name,
        "affiliation": list(ident.affiliations),
        "active": ident.active,
        "cc": code_challenge,
        "ru": redirect_uri,
    }
    return encode_token(SSO_CODE, claims, CODE_TTL)


def redirect_with_code(redirect_uri: str, *, code: str, state: str) -> str:
    separator = "&" if "?" in redirect_uri else "?"
    return redirect_uri + separator + urlencode({"code": code, "state": state})


class MockSsoProvider:
    def __init__(self, authorize_url: str) -> None:
        self.authorize_url = authorize_url

    def authorization_url(
        self, *, state: str, code_challenge: str, redirect_uri: str
    ) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "redirect_uri": redirect_uri,
            }
        )
        return f"{self.authorize_url}?{query}"

    def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> SsoIdentity:
        try:
            claims = decode_token(SSO_CODE, code)
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError(
                "Codul de autorizare SSO este invalid sau a expirat.",
                code="SSO_AUTHENTICATION_FAILED",
            ) from exc

        # PKCE: verifier-ul trebuie să corespundă challenge-ului din cerere.
        if challenge_for(code_verifier) != claims["cc"] or claims["ru"] != redirect_uri:
            raise UnauthorizedError(
                "Codul de autorizare nu aparține acestei autentificări.",
                code="SSO_AUTHENTICATION_FAILED",
            )
        return SsoIdentity(
            email=claims["email"],
            first_name=claims["given_name"],
            last_name=claims["family_name"],
            affiliations=tuple(claims["affiliation"]),
            active=claims["active"],
        )
