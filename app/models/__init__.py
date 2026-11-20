"""Importăm toate modelele, ca SQLAlchemy să le cunoască."""

from app.models.blocked_slot import BlockedSlot
from app.models.booking import Booking
from app.models.enums import (
    BlockReason,
    BookingStatus,
    CancellationSource,
    FacilityType,
    NotificationCategory,
    UserRole,
    WaitlistStatus,
)
from app.models.facility import Facility
from app.models.notification import Notification
from app.models.user import User
from app.models.waitlist_entry import WaitlistEntry

__all__ = [
    "BlockReason",
    "BlockedSlot",
    "Booking",
    "BookingStatus",
    "CancellationSource",
    "Facility",
    "FacilityType",
    "Notification",
    "NotificationCategory",
    "User",
    "UserRole",
    "WaitlistEntry",
    "WaitlistStatus",
]
