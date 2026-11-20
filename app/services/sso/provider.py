"""Contractul unui furnizor SSO (OpenID Connect, Authorization Code + PKCE).

Restul aplicației (AuthService) vorbește doar cu această interfață. Furnizorul
simulat (`mock_provider.py`) și, mai târziu, cel real al universității o
implementează la fel, deci trecerea la SSO-ul real nu schimbă logica de roluri.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SsoIdentity:
    """Identitatea instituțională primită de la furnizorul SSO."""

    email: str
    first_name: str
    last_name: str
    # Afilieri instituționale, ca în `eduPersonAffiliation`:
    # student, faculty, employee, staff, member ...
    affiliations: tuple[str, ...] = ()
    # False pentru conturi dezactivate (absolvit, exmatriculat, plecat).
    active: bool = True


class SsoProvider(Protocol):
    def authorization_url(
        self, *, state: str, code_challenge: str, redirect_uri: str
    ) -> str:
        """Adresa furnizorului către care redirecționăm utilizatorul."""

    def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> SsoIdentity:
        """Schimbă `code` (+ PKCE) pe identitate. Ridică 401 dacă nu e valid."""
