"""Profilul utilizatorului curent."""

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.schemas.user import UserOut, UserUpdate


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def update_profile(self, user: User, data: UserUpdate) -> User:
        """Actualizează doar câmpurile trimise (PATCH)."""
        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        self.db.commit()
        # `updated_at` e setat de un trigger din baza de date, deci reîncărcăm.
        self.db.refresh(user)
        return user

    @staticmethod
    def present(user: User) -> UserOut:
        """Profilul în forma din API (cu câmpurile calculate din Swagger)."""
        external = user.role == UserRole.EXTERNAL
        return UserOut(
            id=user.id,
            name=f"{user.first_name} {user.last_name}",
            email=user.email,
            role=user.role,
            identity_source="external_email" if external else "sso",
            priority=user.role in (UserRole.STUDENT, UserRole.PROFESSOR),
            access_status="active",
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at,
        )
