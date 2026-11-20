"""PKCE (RFC 7636): `code_verifier` și `code_challenge` (metoda S256).

`code_verifier` NU se stochează și NU călătorește prin browser. Se derivă la
nevoie din `nonce`-ul din `state` și din cheia secretă a serverului:
verifier = HMAC(cheie_secretă, nonce). Doar `code_challenge` (hash-ul lui) pleacă
spre furnizor, deci cine interceptează `code` nu poate calcula verifier-ul.
"""

import base64
import hashlib
import hmac

from app.core.security import PKCE, derive_key


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def verifier_for(nonce: str) -> str:
    """43 de caractere URL-safe (cerința RFC 7636: 43-128)."""
    return _b64url(hmac.new(derive_key(PKCE), nonce.encode(), hashlib.sha256).digest())


def challenge_for(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
