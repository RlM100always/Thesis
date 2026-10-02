"""TOTP (RFC 6238) from the standard library only -- no new dependency for MFA.

A secret is a random 20-byte value, base32-encoded for display/QR. The code is
the standard 6-digit, 30-second-step HOTP-over-time construction every
authenticator app (Google Authenticator, Authy, 1Password, ...) implements.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time


def new_totp_secret() -> str:
    """A fresh base32 secret, suitable for an otpauth:// URI or manual entry."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    # Re-pad: base32 requires a length that's a multiple of 8.
    padded = secret_b32 + "=" * (-len(secret_b32) % 8)
    key = base64.b32decode(padded.upper())
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)


def totp_now(secret_b32: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    counter = int((at if at is not None else time.time()) // step)
    return _hotp(secret_b32, counter, digits)


def verify_totp(secret_b32: str, code: str, step: int = 30, digits: int = 6, window: int = 1) -> bool:
    """Accept the current step plus ``window`` steps either side (clock drift)."""
    if not code or not code.isdigit() or len(code) != digits:
        return False
    now = time.time()
    counter = int(now // step)
    for offset in range(-window, window + 1):
        expected = _hotp(secret_b32, counter + offset, digits)
        if hmac.compare_digest(expected, code):
            return True
    return False


def provisioning_uri(secret_b32: str, account_email: str, issuer: str) -> str:
    """``otpauth://`` URI an authenticator app's QR scanner understands."""
    from urllib.parse import quote

    label = quote(f"{issuer}:{account_email}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits=6&period=30"
    )


def new_recovery_codes(count: int = 8) -> list[str]:
    """One-time MFA bypass codes, shown once, stored only as hashes."""
    return [secrets.token_hex(5) for _ in range(count)]
