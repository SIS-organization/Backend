"""Endpoint-uri pentru profilul utilizatorului curent."""

from fastapi import APIRouter

from app.routers.dependencies import CurrentUser, DbSession
from app.schemas.user import UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut, summary="Profilul utilizatorului curent")
def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch(
    "/me", response_model=UserOut, summary="Actualizează profilul (nume, prenume)"
)
def update_me(body: UserUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    updated = UserService(db).update_profile(user, body)
    return UserOut.model_validate(updated)
