"""Autentificare cu SSO: /auth/sso/login și /auth/sso/callback."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.routers.dependencies import DbSession
from app.schemas.auth import AuthTokens
from app.services.auth_service import AuthService
from app.services.sso import SsoProvider, build_sso_provider

router = APIRouter(prefix="/auth", tags=["Auth"])

PROBLEM_RESPONSES = {
    400: {"description": "Cerere invalidă (parametri lipsă, state expirat)."},
    401: {"description": "Codul de autorizare SSO nu este valid."},
    403: {"description": "Contul instituțional nu este eligibil sau este dezactivat."},
}


def get_sso_provider(request: Request) -> SsoProvider:
    settings = get_settings()
    authorize_url = (
        str(request.url_for("mock_idp_authorize"))
        if settings.sso_mode == "mock"
        else None
    )
    return build_sso_provider(settings, mock_authorize_url=authorize_url)


Provider = Annotated[SsoProvider, Depends(get_sso_provider)]


@router.get(
    "/sso/login",
    status_code=302,
    response_class=RedirectResponse,
    summary="Pornește autentificarea SSO USV",
    description=(
        "Redirecționează (302) către furnizorul SSO al universității "
        "(OpenID Connect, Authorization Code + PKCE). Rolul (student / cadru "
        "didactic) este recunoscut automat din identitatea instituțională."
    ),
    responses={
        302: {
            "description": "Redirect către SSO.",
            "headers": {"Location": {"schema": {"type": "string", "format": "uri"}}},
        },
        400: PROBLEM_RESPONSES[400],
    },
)
def sso_login(
    db: DbSession,
    provider: Provider,
    redirect_to: Annotated[
        str | None,
        Query(
            alias="redirectTo",
            description="Ruta frontend către care se revine după autentificare.",
            examples=["/facilitati"],
        ),
    ] = None,
) -> RedirectResponse:
    url = AuthService(db, provider, get_settings()).start_login(redirect_to)
    return RedirectResponse(url, status_code=302)


@router.get(
    "/sso/callback",
    response_model=AuthTokens,
    summary="Callback SSO",
    description=(
        "Primește `code` și `state` de la SSO, creează/actualizează utilizatorul "
        "local și emite token-urile (JWT cu `sub`, `role`, `exp`)."
    ),
    responses=PROBLEM_RESPONSES,
)
def sso_callback(
    response: Response,
    db: DbSession,
    provider: Provider,
    code: Annotated[str, Query(min_length=1, max_length=4096)],
    state: Annotated[str, Query(min_length=1, max_length=4096)],
) -> AuthTokens:
    # Răspunsul conține token-uri: nu are voie să fie păstrat în cache (RFC 6749).
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return AuthService(db, provider, get_settings()).complete_login(code, state)
