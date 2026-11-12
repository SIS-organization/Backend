"""Scheme pentru facilități."""

from app.models.enums import FacilityType
from app.schemas.common import CamelModel


class FacilitySummary(CamelModel):
    """Facilitatea, în forma scurtă folosită în interiorul unei rezervări."""

    id: int
    name: str
    location: str


class FacilityOut(FacilitySummary):
    """Facilitatea completă."""

    type: FacilityType
    capacity: int
    is_active: bool


class FacilityList(CamelModel):
    items: list[FacilityOut]
