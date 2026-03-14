"""
Security helpers.

Password hashing prefers bcrypt when available, but gracefully falls back to
Werkzeug's password hashing so the app can run even if bcrypt isn't installed in
the active environment.
"""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

try:
    import bcrypt as _bcrypt  # type: ignore
except Exception:  # pragma: no cover
    _bcrypt = None


_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    if _bcrypt is not None:
        return _bcrypt.hashpw(
            password.encode("utf-8"), _bcrypt.gensalt()
        ).decode("utf-8")
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def check_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False

    if hashed.startswith(_BCRYPT_PREFIXES):
        if _bcrypt is None:
            return False
        return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    try:
        return check_password_hash(hashed, password)
    except Exception:
        return False

