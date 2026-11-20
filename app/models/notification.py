"""Modelul (tabela) `notifications`: notificările din aplicație."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import NotificationCategory, pg_enum
from app.models.mixins import TimestampMixin


class Notification(TimestampMixin, Base):
    """O notificare pentru un utilizator (ex. oferta din lista de așteptare)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category: Mapped[NotificationCategory] = mapped_column(
        pg_enum(NotificationCategory, "notification_category")
    )
    title: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))
    waitlist_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("waitlist_entries.id")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
