"""Scheme pentru autentificare (conform schemei `AuthTokens` din Swagger)."""

from app.schemas.common import CamelModel
from app.schemas.user import UserOut


class AuthTokens(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # secunde
    user: UserOut
    # Extra față de Swagger: ruta frontend cerută la login (`redirectTo`), ca
    # frontend-ul să știe unde îl duce după autentificare.
    redirect_to: str | None = None
