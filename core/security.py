"""
Password hashing (SRS FR-AUTH-04: never store plain-text passwords).

Uses PBKDF2-HMAC-SHA256 from Python's standard library `hashlib` - no
third-party dependency required, and it is the same primitive Django's
default password hasher is built on, so migrating to Django's auth
system later needs no change in approach.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 260_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS)
    return derived.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)
