"""Password hashing with the standard library (scrypt).

scrypt is memory-hard and needs no extra dependency. The stored format is
``scrypt$N$r$p$salt_b64$hash_b64`` so parameters can be raised later and old
hashes still verify.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

_N, _R, _P, _DKLEN = 2**14, 8, 1, 32


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time check. A missing or malformed hash never verifies."""
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def hash_setup_token(raw: str) -> str:
    """Setup tokens are stored as SHA-256 digests, so a database leak cannot be replayed."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_setup_token() -> tuple[str, str]:
    """Return ``(raw, digest)``. The raw token is shown once; only the digest is kept."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_setup_token(raw)


# Verified against when the email is unknown, so an unknown account costs the
# same time as a wrong password and cannot be told apart by timing.
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")
