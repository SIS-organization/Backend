"""Furnizorul SSO SIMULAT: pagina „universității” unde alegi contul.

Se montează DOAR când `SSO_MODE=mock` și nu apare în Swagger. Imită endpoint-ul
`authorize` al unui furnizor OpenID Connect real: validează cererea (inclusiv
`redirect_uri` exact, cum fac furnizorii reali) și întoarce utilizatorul cu
`code` și `state`.
"""

import re
from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.core.exceptions import AppError, UnauthorizedError
from app.services.sso.mock_provider import (
    MOCK_ACCOUNTS,
    find_account,
    issue_code,
    redirect_with_code,
)

router = APIRouter(prefix="/auth/sso/mock", include_in_schema=False)

# SHA-256 în base64url, fără „=”: exact 43 de caractere.
CHALLENGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _invalid(detail: str) -> AppError:
    return AppError(detail, code="INVALID_SSO_REQUEST")


@router.get("/authorize", name="mock_idp_authorize", response_model=None)
def authorize(
    request: Request,
    state: Annotated[str, Query(min_length=1, max_length=4096)],
    code_challenge: Annotated[str, Query()],
    redirect_uri: Annotated[str, Query()],
    response_type: str = "code",
    code_challenge_method: str = "S256",
    login_hint: str | None = None,
) -> HTMLResponse | RedirectResponse:
    if response_type != "code":
        raise _invalid("Se acceptă doar response_type=code.")
    if code_challenge_method != "S256" or not CHALLENGE_PATTERN.match(code_challenge):
        raise _invalid("PKCE este obligatoriu (code_challenge_method=S256).")
    if redirect_uri != get_settings().sso_redirect_uri:
        raise _invalid("redirect_uri nu este înregistrat la furnizor.")

    if login_hint is None:
        return HTMLResponse(_account_picker(request))

    account = find_account(login_hint)
    if account is None:
        raise UnauthorizedError(
            "Cont necunoscut la furnizorul SSO simulat.",
            code="SSO_AUTHENTICATION_FAILED",
        )
    code = issue_code(account, code_challenge=code_challenge, redirect_uri=redirect_uri)
    return RedirectResponse(
        redirect_with_code(redirect_uri, code=code, state=state), status_code=302
    )


def _account_picker(request: Request) -> str:
    base = dict(request.query_params)
    rows = []
    for account in MOCK_ACCOUNTS:
        ident = account.identity
        link = "?" + urlencode({**base, "login_hint": ident.email})
        rows.append(
            f'<li><a href="{escape(link)}"><b>{escape(ident.email)}</b></a>'
            f" &mdash; {escape(account.description)}</li>"
        )
    return (
        "<!doctype html><html lang='ro'><meta charset='utf-8'>"
        "<title>SSO USV (simulat)</title>"
        "<body style='font-family:sans-serif;max-width:42rem;margin:2rem auto'>"
        "<h1>SSO USV &mdash; simulare</h1>"
        "<p><b>Mediu de dezvoltare.</b> Alege contul cu care te autentifici:</p>"
        f"<ul>{''.join(rows)}</ul></body></html>"
    )
