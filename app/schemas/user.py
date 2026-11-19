"""Scheme pentru profilul utilizatorului (ce intră și ce iese din API)."""

from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints, field_serializer, model_validator

from app.core.time import to_api
from app.models.enums import UserRole
from app.schemas.common import CamelModel

# Nume curățate de spații și de lungime rezonabilă (coloana are varchar(50)).
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]


class UserOut(CamelModel):
    """Profilul utilizatorului. Nu conține parola sau alte date sensibile."""

    id: int
    first_name: str
    last_name: str
    email: str
    role: UserRole
    created_at: datetime

    @field_serializer("created_at")
    def _with_offset(self, value: datetime) -> str:
        return to_api(value).isoformat()


class UserUpdate(CamelModel):
    """Corpul pentru PATCH /users/me. Rolul și e-mailul nu se pot schimba aici."""

    first_name: Name | None = Field(default=None)
    last_name: Name | None = Field(default=None)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "UserUpdate":
        if self.first_name is None and self.last_name is None:
            raise ValueError("Trimite cel puțin un câmp: firstName sau lastName.")
        return self
