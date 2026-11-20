"""Token-uri JWT și chei derivate.

Toate token-urile se semnează cu HS256, dar fiecare TIP de token are propria
cheie, derivată din `JWT_SECRET` (HMAC). Astfel un token de un tip (de exemplu
`state`-ul SSO sau codul simulat) nu poate fi folosit niciodată ca alt tip
(de exemplu ca token de acces), chiar dacă are o semnătură „validă".

Claim-urile token-ului de acces respectă Swagger-ul: `sub` (id-ul utilizatorului),
`role` și `exp`. În plus: `iat` și `token_use` (tipul token-ului).
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings
from app.models.enums import UserRole

ALGORITHM = "HS256"

ACCESS = "access"
REFRESH = "refresh"
SSO_STATE = "sso_state"
SSO_CODE = "sso_code"
PKCE = "pkce"


def derive_key(purpose: str) -> bytes:
    """Cheie de 32 de octeți, specifică unui scop, derivată din JWT_SECRET."""
    secret = get_settings().jwt_secret.encode()
    return hmac.new(secret, f"usv-sport:{purpose}".encode(), hashlib.sha256).digest()


def encode_token(purpose: str, claims: dict[str, Any], ttl: timedelta) -> str:
    """Semnează un token de tipul `purpose`, valabil `ttl`."""
    now = datetime.now(timezone.utc)
    payload = {**claims, "token_use": purpose, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, derive_key(purpose), algorithm=ALGORITHM)


def decode_token(purpose: str, token: str) -> dict[str, Any]:
    """Verifică semnătura, expirarea și tipul. Ridică `jwt.InvalidTokenError`."""
    payload = jwt.decode(
        token,
        derive_key(purpose),
        algorithms=[ALGORITHM],  # niciodată „none" sau alt algoritm
        options={"require": ["exp", "iat", "token_use"]},
    )
    if payload["token_use"] != purpose:
        raise jwt.InvalidTokenError("Tipul token-ului nu este cel așteptat.")
    return payload


def access_token_ttl() -> timedelta:
    return timedelta(minutes=get_settings().jwt_access_ttl_minutes)


def create_access_token(user_id: int, role: UserRole) -> str:
    """JWT de acces: `sub`, `role`, `exp` (Swagger) + `iat`, `token_use`."""
    return encode_token(
        ACCESS, {"sub": str(user_id), "role": role.value}, access_token_ttl()
    )


def create_refresh_token(user_id: int) -> str:
    """Token de reînnoire (fără rol: rolul se citește din baza de date)."""
    ttl = timedelta(days=get_settings().jwt_refresh_ttl_days)
    return encode_token(REFRESH, {"sub": str(user_id)}, ttl)


def decode_access_token(token: str) -> dict[str, Any]:
    """Token de acces valid sau `jwt.InvalidTokenError` (expirat, alterat etc.)."""
    return decode_token(ACCESS, token)
