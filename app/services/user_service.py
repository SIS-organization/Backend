"""Profilul utilizatorului curent."""

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserUpdate


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
