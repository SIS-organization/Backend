"""Modelul (tabela) `blocked_slots`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import BlockReason, pg_enum
from app.models.mixins import TimestampMixin


class BlockedSlot(TimestampMixin, Base):
    """Un interval blocat (curs, eveniment USV, mentenanță) la o facilitate."""

    __tablename__ = "blocked_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[BlockReason] = mapped_column(pg_enum(BlockReason, "block_reason"))
    description: Mapped[str | None] = mapped_column(Text)
