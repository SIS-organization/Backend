"""Configurarea aplicației, citită din variabile de mediu / fișierul .env."""

from datetime import time
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Setările aplicației. Valorile vin din .env (vezi .env.example)."""

    app_name: str = "USV Sport API"
    app_version: str = "0.1.0"
    database_url: str
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Regulile de rezervare (pot fi schimbate din .env, fără modificări de cod).
    timezone: str = "Europe/Bucharest"
    opening_time: time = time(8, 0)
    closing_time: time = time(21, 0)
    slot_minutes: int = 60
    min_cancel_notice_hours: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Returnează setările (create o singură dată)."""
    return Settings()
