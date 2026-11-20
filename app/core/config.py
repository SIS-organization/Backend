"""Configurarea aplicației, citită din variabile de mediu / fișierul .env."""

from datetime import time
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Setările aplicației. Valorile vin din .env (vezi .env.example)."""

    app_name: str = "USV Sport API"
    app_version: str = "0.1.0"
    database_url: str
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Regulile de rezervare (pot fi schimbate din .env, fără modificări de cod).
    timezone: str = "Europe/Bucharest"
    opening_time: time = time(8, 0)
    closing_time: time = time(21, 0)
    slot_minutes: int = 60
    min_cancel_notice_hours: int = 2

    # Autentificare (JWT). Cheia vine DOAR din .env, nu are valoare implicită:
    # fără ea aplicația nu pornește, ca să nu rulăm vreodată cu o cheie cunoscută.
    jwt_secret: str = Field(min_length=32)
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 7

    # SSO universitar. `mock` = furnizor simulat (dezvoltare / demo, nu producție);
    # `oidc` este rezervat pentru SSO-ul real al universității (încă neconfigurat).
    sso_mode: Literal["mock", "oidc"] = "mock"
    # Adresa la care furnizorul SSO trimite utilizatorul după autentificare
    # (cu `code` și `state`). Pentru frontend: ruta lui, care apoi apelează
    # GET /v1/auth/sso/callback.
    sso_redirect_uri: str = "http://localhost:8000/v1/auth/sso/callback"
    sso_state_ttl_minutes: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Returnează setările (create o singură dată)."""
    return Settings()
