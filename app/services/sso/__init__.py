"""Autentificare SSO: furnizori (simulat / real), PKCE și logica de roluri."""

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.sso.mock_provider import MockSsoProvider
from app.services.sso.provider import SsoIdentity, SsoProvider
from app.services.sso.roles import role_for_identity

__all__ = [
    "SsoIdentity",
    "SsoProvider",
    "build_sso_provider",
    "role_for_identity",
]


def build_sso_provider(
    settings: Settings, *, mock_authorize_url: str | None
) -> SsoProvider:
    """Furnizorul ales prin `SSO_MODE` (din .env)."""
    if settings.sso_mode == "mock" and mock_authorize_url:
        return MockSsoProvider(mock_authorize_url)
    # `oidc`: se adaugă aici când universitatea oferă datele de conectare.
    raise AppError(
        "SSO-ul universității nu este configurat.",
        status_code=501,
        title="Not Implemented",
        code="SSO_NOT_CONFIGURED",
    )
