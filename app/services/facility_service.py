"""Facilitățile (doar citire, în acest sprint)."""

from sqlalchemy.orm import Session

from app.models import Facility
from app.repositories.facility_repository import FacilityRepository


class FacilityService:
    def __init__(self, db: Session) -> None:
        self.facilities = FacilityRepository(db)

    def list_all(self) -> list[Facility]:
        return self.facilities.list_all()
