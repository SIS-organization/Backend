"""Autentificarea cu SSO: pornirea fluxului și finalizarea lui (callback).

Fluxul (OpenID Connect, Authorization Code + PKCE):

1. `start_login`: generăm `nonce`, calculăm `code_challenge` (PKCE) și un `state`
   semnat (nonce + ruta cerută + expirare). Redirecționăm utilizatorul la SSO.
2. SSO îl autentifică și îl trimite înapoi cu `code` și `state`.
3. `complete_login`: verificăm `state`, recalculăm `code_verifier` din nonce,
   schimbăm `code` pe identitate, găsim/creăm utilizatorul local cu rolul
   corect și emitem JWT-urile.

Nu stocăm nimic între pașii 1 și 3 (starea e în `state`-ul semnat), deci
funcționează la fel cu mai multe procese ale serverului.
"""

import secrets
from datetime import timedelta

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError, ForbiddenError, UnauthorizedError
from app.core.security import (
    SSO_STATE,
    access_token_ttl,
    create_access_token,
    create_refresh_token,
    decode_token,
    encode_token,
)
from app.models import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokens
from app.services.sso import SsoIdentity, SsoProvider, role_for_identity
from app.services.sso.pkce import challenge_for, verifier_for
from app.services.user_service import UserService

# Conturile SSO nu au parolă locală. Valoarea nu este un hash valid, deci nu se
# poate autentifica nimeni cu ea (la fel ca `!seed-fara-login` din seed.sql).
SSO_PASSWORD_MARKER = "!sso-fara-parola"

MAX_REDIRECT_LENGTH = 200


def validate_redirect_to(redirect_to: str | None) -> str | None:
    """Acceptă doar rute interne ale aplicației (apărare contra „open redirect”)."""
    if redirect_to is None or redirect_to == "":
        return None
    unsafe = (
        not redirect_to.startswith("/")
        or redirect_to.startswith("//")
        or "\\" in redirect_to
        or len(redirect_to) > MAX_REDIRECT_LENGTH
        or any(ch.isspace() or ord(ch) < 32 for ch in redirect_to)
    )
    if unsafe:
        raise AppError(
            "`redirectTo` trebuie să fie o rută internă, de forma /facilitati.",
            code="INVALID_REDIRECT",
        )
    return redirect_to


def _clean_name(value: str, fallback: str) -> str:
    """Numele vin de la SSO; coloanele sunt NOT NULL și au varchar(50)."""
    return (value or "").strip()[:50] or fallback[:50]


class AuthService:
    def __init__(self, db: Session, provider: SsoProvider, settings: Settings) -> None:
        self.db = db
        self.provider = provider
        self.settings = settings
        self.users = UserRepository(db)

    # ---------- pasul 1: /auth/sso/login ----------
    def start_login(self, redirect_to: str | None) -> str:
        """Adresa SSO către care redirecționăm utilizatorul."""
        route = validate_redirect_to(redirect_to)
        nonce = secrets.token_urlsafe(16)
        state = encode_token(
            SSO_STATE,
            {"nonce": nonce, "redirect_to": route},
            timedelta(minutes=self.settings.sso_state_ttl_minutes),
        )
        return self.provider.authorization_url(
            state=state,
            code_challenge=challenge_for(verifier_for(nonce)),
            redirect_uri=self.settings.sso_redirect_uri,
        )

    # ---------- pasul 3: /auth/sso/callback ----------
    def complete_login(self, code: str, state: str) -> AuthTokens:
        try:
            payload = decode_token(SSO_STATE, state)
        except jwt.InvalidTokenError as exc:
            raise AppError(
                "Autentificarea a expirat sau cererea nu este validă. "
                "Pornește din nou autentificarea.",
                code="INVALID_SSO_STATE",
            ) from exc

        identity = self.provider.exchange_code(
            code=code,
            code_verifier=verifier_for(payload["nonce"]),
            redirect_uri=self.settings.sso_redirect_uri,
        )
        user = self._sign_in(identity)
        return AuthTokens(
            access_token=create_access_token(user.id, user.role),
            refresh_token=create_refresh_token(user.id),
            expires_in=int(access_token_ttl().total_seconds()),
            user=UserService.present(user),
            redirect_to=payload.get("redirect_to"),
        )

    # ---------- utilizatorul local ----------
    def _sign_in(self, identity: SsoIdentity) -> User:
        """Verifică eligibilitatea și creează / actualizează contul local."""
        email = identity.email.strip().lower()
        if not email or len(email) > 100:
            raise UnauthorizedError(
                "Identitatea primită de la SSO este invalidă.",
                code="SSO_AUTHENTICATION_FAILED",
            )
        if not identity.active:
            raise ForbiddenError(
                "Contul instituțional este dezactivat.", code="ACCOUNT_DISABLED"
            )
        role = role_for_identity(identity)
        if role is None:
            raise ForbiddenError(
                "Contul nu este un cont instituțional USV (student sau cadru "
                "didactic). Publicul extern își face cont separat.",
                code="ACCOUNT_NOT_ELIGIBLE",
            )

        first = _clean_name(identity.first_name, email.split("@")[0])
        last = _clean_name(identity.last_name, "-")
        user = self.users.get_by_email(email)

        if user is None:
            return self._create(email, first, last, role)
        return self._update(user, first, last, role)

    def _create(self, email: str, first: str, last: str, role: UserRole) -> User:
        user = User(
            email=email,
            first_name=first,
            last_name=last,
            password_hash=SSO_PASSWORD_MARKER,
            role=role,
        )
        self.users.add(user)
        try:
            self.db.commit()
        except IntegrityError:
            # Două prime autentificări simultane: a câștigat cealaltă.
            self.db.rollback()
            existing = self.users.get_by_email(email)
            if existing is None:
                raise
            return self._update(existing, first, last, role)
        self.db.refresh(user)
        return user

    def _update(self, user: User, first: str, last: str, role: UserRole) -> User:
        if user.role == UserRole.EXTERNAL:
            raise ForbiddenError(
                "Există deja un cont extern cu acest e-mail. Contactează "
                "administratorul pentru a-l transforma în cont instituțional.",
                code="ACCOUNT_CONFLICT",
            )
        # Rolul vine din instituție (student <-> cadru didactic), dar un
        # administrator rămâne administrator.
        new_role = user.role if user.role == UserRole.ADMINISTRATOR else role
        changed = (user.first_name, user.last_name, user.role) != (
            first,
            last,
            new_role,
        )
        if changed:
            user.first_name, user.last_name, user.role = first, last, new_role
            self.db.commit()
            self.db.refresh(user)
        return user
