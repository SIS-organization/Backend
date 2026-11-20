"""Acces la tabela `users`."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        """Caută după e-mail, fără diferență între litere mari și mici."""
        query = select(User).where(func.lower(User.email) == email.strip().lower())
        return self.db.scalars(query).first()

    def add(self, user: User) -> None:
        self.db.add(user)
