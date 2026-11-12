"""Dependențe comune pentru routere."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    """Utilizatorul curent, identificat temporar prin antetul `X-User-Id`.

    Provizoriu, până la autentificarea JWT din Epic 3: frontend-ul trimite
    id-ul utilizatorului. Atunci va fi schimbată doar această funcție.
    """
    if x_user_id is None or not x_user_id.isdigit():
        raise UnauthorizedError("Lipsește antetul X-User-Id (număr întreg).")
    user = db.get(User, int(x_user_id))
    if user is None:
        raise UnauthorizedError("Utilizator necunoscut.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
