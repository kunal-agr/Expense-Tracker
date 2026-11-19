import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import settings

_pwd_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash password using Argon2."""
    return _pwd_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2 hash."""
    try:
        return _pwd_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_refresh_token(token: str) -> str:
    """Store refresh token hashed with SHA-256 in the database."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """Generate cryptographically secure random token."""
    return secrets.token_urlsafe(64)


def create_access_token(user_id: int, username: str) -> str:
    """Create short-lived JWT access token (15 minutes)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> Dict[str, Any] | None:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None
