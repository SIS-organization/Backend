"""Dependențe comune: sesiunea DB, utilizatorul autentificat (JWT) și rolurile.

Autentificarea se face prin antetul `Authorization: Bearer <JWT>`, cu token-ul
emis de `/auth/sso/callback`. Orice endpoint care are nevoie de un utilizator
declară `CurrentUser`; orice endpoint rezervat anumitor roluri folosește
`require_roles(...)`. Un endpoint care nu declară niciuna dintre ele este public,
iar `tests/test_authorization.py` verifică lista endpoint-urilor publice.
"""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models import User, UserRole

DbSession = Annotated[Session, Depends(get_db)]

# `auto_error=False`: eroarea 401 o producem noi, în formatul RFC 7807 din Swagger.
# Declararea schemei face să apară butonul „Authorize” în Swagger UI (/docs).
bearer_scheme = HTTPBearer(
    scheme_name="bearerAuth",
    bearerFormat="JWT",
    auto_error=False,
    description=(
        "JWT emis după autentificarea SSO (`/auth/sso/login`). "
        "Claim-uri: `sub`, `role`, `exp`. Endpoint-urile `/admin/*` "
        "necesită `role=administrator`."
    ),
)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Utilizatorul din JWT, sau 401 dacă cererea nu este autentificată.

    401 (cu `WWW-Authenticate: Bearer`) pentru: antet lipsă sau de altă schemă,
    token alterat, expirat, de alt tip (de exemplu cel de reînnoire) sau
    semnat cu altă cheie, și utilizator care nu mai există.

    Rolul folosit la autorizare este cel din BAZA DE DATE, nu cel din token:
    dacă un administrator este retrogradat, token-ul lui încă valid nu îi mai
    dă drepturi de administrator.
    """
    if credentials is None:
        raise UnauthorizedError("Autentifică-te cu contul USV.")
    try:
        claims = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Sesiunea a expirat. Autentifică-te din nou.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token de autentificare invalid.") from exc

    subject = claims.get("sub", "")
    if not (isinstance(subject, str) and subject.isascii() and subject.isdigit()):
        raise UnauthorizedError("Token de autentificare invalid.")
    if claims.get("role") not in {role.value for role in UserRole}:
        raise UnauthorizedError("Token de autentificare invalid.")

    user = db.get(User, int(subject))
    if user is None:
        raise UnauthorizedError("Contul din token nu mai există.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependență care permite accesul doar rolurilor date (altfel 403).

    Include autentificarea: fără token valid răspunsul este 401, nu 403.
    Folosire: `Depends(require_roles(UserRole.ADMINISTRATOR))`, pe un endpoint
    sau pe un întreg router.
    """
    if not roles:
        raise ValueError("require_roles are nevoie de cel puțin un rol.")
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Nu ai permisiunea necesară.", code="FORBIDDEN")
        return user

    return dependency


require_admin = require_roles(UserRole.ADMINISTRATOR)
