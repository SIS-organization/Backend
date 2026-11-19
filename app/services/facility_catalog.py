"""Sporturile și dotările fiecărei facilități (conform codurilor din Swagger).

Baza de date nu păstrează încă sporturile și dotările, așa că le deducem din
tipul facilității. Dacă ele ajung în baza de date, se schimbă doar acest fișier.
"""

from dataclasses import dataclass
from enum import Enum

from app.models.enums import FacilityType


class SportCode(str, Enum):
    FOOTBALL = "football"
    FITNESS = "fitness"
    SWIMMING = "swimming"
    BASKETBALL = "basketball"
    VOLLEYBALL = "volleyball"
    TENNIS = "tennis"


class AmenityCode(str, Enum):
    CHANGING_ROOMS = "changing_rooms"
    SHOWERS = "showers"
    FLOODLIGHTS = "floodlights"
    ACCESSIBILITY = "accessibility"
    CARDIO = "cardio"
    WEIGHTS = "weights"
    SWIM_LANES = "swim_lanes"
    BLEACHERS = "bleachers"
    SPORTS_FLOORING = "sports_flooring"


SPORT_LABELS = {
    SportCode.FOOTBALL: "Fotbal",
    SportCode.FITNESS: "Fitness",
    SportCode.SWIMMING: "Înot",
    SportCode.BASKETBALL: "Baschet",
    SportCode.VOLLEYBALL: "Volei",
    SportCode.TENNIS: "Tenis",
}

AMENITY_LABELS = {
    AmenityCode.CHANGING_ROOMS: "Vestiare",
    AmenityCode.SHOWERS: "Dușuri",
    AmenityCode.FLOODLIGHTS: "Nocturnă",
    AmenityCode.ACCESSIBILITY: "Accesibilitate",
    AmenityCode.CARDIO: "Aparate cardio",
    AmenityCode.WEIGHTS: "Greutăți",
    AmenityCode.SWIM_LANES: "Culoare de înot",
    AmenityCode.BLEACHERS: "Tribune",
    AmenityCode.SPORTS_FLOORING: "Parchet sportiv",
}


@dataclass(frozen=True)
class FacilityProfile:
    description: str
    sports: tuple[SportCode, ...]
    amenities: tuple[AmenityCode, ...]


PROFILES: dict[FacilityType, FacilityProfile] = {
    FacilityType.FOOTBALL_FIELD: FacilityProfile(
        "Teren de fotbal · Vestiare · Nocturnă",
        (SportCode.FOOTBALL,),
        (AmenityCode.CHANGING_ROOMS, AmenityCode.FLOODLIGHTS),
    ),
    FacilityType.GYM: FacilityProfile(
        "Aparate cardio · Greutăți · Vestiare",
        (SportCode.FITNESS,),
        (
            AmenityCode.CHANGING_ROOMS,
            AmenityCode.SHOWERS,
            AmenityCode.CARDIO,
            AmenityCode.WEIGHTS,
        ),
    ),
    FacilityType.SWIMMING_POOL: FacilityProfile(
        "Bazin acoperit · Culoare de înot · Vestiare",
        (SportCode.SWIMMING,),
        (
            AmenityCode.CHANGING_ROOMS,
            AmenityCode.SHOWERS,
            AmenityCode.SWIM_LANES,
            AmenityCode.ACCESSIBILITY,
        ),
    ),
    FacilityType.SPORTS_HALL: FacilityProfile(
        "Sală polivalentă · Baschet · Volei",
        (SportCode.BASKETBALL, SportCode.VOLLEYBALL),
        (
            AmenityCode.CHANGING_ROOMS,
            AmenityCode.BLEACHERS,
            AmenityCode.SPORTS_FLOORING,
            AmenityCode.ACCESSIBILITY,
        ),
    ),
}
