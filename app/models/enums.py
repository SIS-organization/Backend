"""Tipurile enumerate (aceleași valori ca tipurile din PostgreSQL)."""

import enum

from sqlalchemy import Enum as SAEnum


class UserRole(str, enum.Enum):
    """Rolul unui utilizator."""

    STUDENT = "student"
    PROFESSOR = "professor"
    EXTERNAL = "external"
    ADMINISTRATOR = "administrator"


class FacilityType(str, enum.Enum):
    """Tipul unei facilități."""

    FOOTBALL_FIELD = "football_field"
    GYM = "gym"
    SWIMMING_POOL = "swimming_pool"
    SPORTS_HALL = "sports_hall"


class BookingStatus(str, enum.Enum):
    """Starea unei rezervări."""

    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class BlockReason(str, enum.Enum):
    """Motivul unei blocări de interval."""

    UNIVERSITY_COURSE = "university_course"
    UNIVERSITY_EVENT = "university_event"
    MAINTENANCE = "maintenance"
    REPAIR = "repair"
    CLEANING = "cleaning"
    OTHER = "other"


def pg_enum(enum_class: type[enum.Enum], name: str) -> SAEnum:
    """Leagă o clasă Enum de tipul enumerat existent în PostgreSQL.

    `create_type=False`: tipul este creat de schema.sql, nu de SQLAlchemy.
    """
    return SAEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        create_type=False,
    )
