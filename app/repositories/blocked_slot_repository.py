"""Acces la tabela `blocked_slots`."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BlockedSlot


class BlockedSlotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_overlapping(
        self, facility_id: int, start: datetime, end: datetime
    ) -> BlockedSlot | None:
        """Primul interval blocat care se suprapune cu [start, end)."""
        return self.db.scalars(
            select(BlockedSlot)
            .where(
                BlockedSlot.facility_id == facility_id,
                BlockedSlot.start_time < end,
                BlockedSlot.end_time > start,
            )
            .limit(1)
        ).first()
