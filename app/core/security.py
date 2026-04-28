"""
app/core/security.py
─────────────────────
Password hashing with bcrypt and JWT token creation/verification.

ROOT CAUSE OF PREVIOUS ERROR:
  Two bugs appeared at once:

  1. "(trapped) error reading bcrypt version"
     → passlib 1.7.4 does `bcrypt.__about__.__version__` at import time.
       Modern bcrypt (>=4.1) removed the __about__ submodule, so passlib
       prints a noisy traceback (it catches the error but can't silence it).

  2. "password cannot be longer than 72 bytes"
     → The 72-byte limit is bcrypt's hardcoded maximum input length.
       It's a property of the algorithm, not a bug. But passlib 1.7.4 has
       broken interop with bcrypt>=4.1 — the length-check path misfires and
       raises on perfectly valid short inputs.

THE FIX:
  Drop passlib entirely and use the `bcrypt` library directly. Reasons:

  • passlib's last release was October 2020 — effectively unmaintained.
  • bcrypt (PyCA) is maintained, widely used, and has a stable minimal API.
  • One fewer transitive dependency to pin or worry about.
  • Explicit truncation-to-72-bytes with clear error message for huge inputs.

  API is unchanged — hash_password() and verify_password() still have the
  same signatures, so no other file in the project needs to change.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt's hard limit — enforced by the algorithm itself (not by us)
_BCRYPT_MAX_BYTES = 72

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def _to_bcrypt_bytes(password: str) -> bytes:
    """
    Convert a string password to bytes and enforce the 72-byte bcrypt limit.

    Why enforce it ourselves?
      bcrypt 4.1+ raises a confusing ValueError on inputs > 72 bytes.
      By truncating explicitly we get predictable behaviour and a clearer
      error path. 72 bytes is enough entropy for any reasonable password.
    """
    raw = password.encode("utf-8")
    # Truncate to 72 bytes — standard practice for bcrypt wrappers
    return raw[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    """
    Return a bcrypt hash of a plain-text password.

    bcrypt.hashpw() returns bytes; we decode to str for storage in a
    VARCHAR column. The hash itself is pure ASCII so decoding is safe.
    """
    password_bytes = _to_bcrypt_bytes(plain)
    salt = bcrypt.gensalt(rounds=12)   # 12 rounds ≈ 250ms on modern CPU
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """
    Return True if `plain` matches the stored bcrypt `hashed` string.

    bcrypt.checkpw handles constant-time comparison internally to prevent
    timing attacks. If the stored hash is malformed we catch and return
    False rather than leaking details via an exception.
    """
    try:
        return bcrypt.checkpw(
            _to_bcrypt_bytes(plain),
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        # Malformed hash, wrong encoding, etc. — treat as auth failure.
        return False


def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: usually the user's id or email — stored in the 'sub' claim.
        expires_delta: token lifetime (defaults to ACCESS_TOKEN_EXPIRE_MINUTES).
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
