"""Modelul (tabela) `waitlist_entries`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import WaitlistStatus, pg_enum
from app.models.facility import Facility
from app.models.mixins import TimestampMixin
from app.models.user import User


class WaitlistEntry(TimestampMixin, Base):
    """Un utilizator care așteaptă un interval ocupat la o facilitate."""

    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[WaitlistStatus] = mapped_column(
        pg_enum(WaitlistStatus, "waitlist_status"),
        server_default=text("'active'"),
    )
    replace_booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))
    offered_at: Mapped[datetime | None] = mapped_column(DateTime)
    offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship()
    facility: Mapped[Facility] = relationship()
