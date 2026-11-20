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


class CancellationSource(str, enum.Enum):
    """Cine a anulat rezervarea."""

    USER = "user"
    ADMINISTRATOR = "administrator"
    MAINTENANCE = "maintenance"
    UNIVERSITY_ACTIVITY = "university_activity"
    SYSTEM = "system"


class WaitlistStatus(str, enum.Enum):
    """Starea unei intrări pe lista de așteptare."""

    ACTIVE = "active"  # așteaptă să se elibereze un loc
    OFFERED = "offered"  # a primit oferta și trebuie să răspundă
    FULFILLED = "fulfilled"  # a acceptat: rezervarea a fost creată / mutată
    DECLINED = "declined"  # a refuzat oferta („Păstrez ora")
    EXPIRED = "expired"  # oferta sau intervalul au expirat
    CANCELLED = "cancelled"  # a ieșit de pe listă


class NotificationCategory(str, enum.Enum):
    """Categoria unei notificări (ca în Swagger)."""

    BOOKING_CONFIRMATION = "booking_confirmation"
    REMINDER = "reminder"
    CANCELLATION = "cancellation"
    WAITLIST_OFFER = "waitlist_offer"
    UNIVERSITY_ACTIVITY = "university_activity"
    MAINTENANCE = "maintenance"
    INCIDENT_URGENT = "incident_urgent"
    REOPENING = "reopening"


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
