"""Modelul (tabela) `bookings`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BookingStatus, CancellationSource, pg_enum
from app.models.facility import Facility
from app.models.mixins import TimestampMixin
from app.models.user import User


class Booking(TimestampMixin, Base):
    """O rezervare a unui utilizator la o facilitate, pe un interval orar."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[BookingStatus] = mapped_column(
        pg_enum(BookingStatus, "booking_status"),
        server_default=text("'confirmed'"),
    )
    early_released_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_by: Mapped[CancellationSource | None] = mapped_column(
        pg_enum(CancellationSource, "cancellation_source")
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    # Setat când rezervarea a rezultat dintr-o mutare (lista de așteptare):
    # înlocuiește rezervarea indicată, nu se adaugă una nouă.
    replaced_booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"))

    user: Mapped[User] = relationship()
    facility: Mapped[Facility] = relationship()
