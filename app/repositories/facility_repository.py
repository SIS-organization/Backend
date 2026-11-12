"""Acces la tabela `facilities`."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Facility


class FacilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Facility]:
        return list(self.db.scalars(select(Facility).order_by(Facility.id)))

    def get_for_update(self, facility_id: int) -> Facility | None:
        """Citește facilitatea și o blochează până la commit.

        Cererile simultane pentru aceeași facilitate așteaptă una după alta,
        deci două persoane nu pot lua ultimul loc liber în același timp.
        """
        return self.db.scalar(
            select(Facility).where(Facility.id == facility_id).with_for_update()
        )
