"""Modelul (tabela) `facilities`."""

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import FacilityType, pg_enum
from app.models.mixins import TimestampMixin


class Facility(TimestampMixin, Base):
    """O facilitate sportivă (teren, sală fitness, bazin, sală de sport)."""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[FacilityType] = mapped_column(pg_enum(FacilityType, "facility_type"))
    # Câte rezervări simultane suportă (ex. 4 culoare la bazin).
    capacity: Mapped[int] = mapped_column(server_default=text("1"))
    location: Mapped[str] = mapped_column(String(150))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
