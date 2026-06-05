from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.settings import Settings, get_settings

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=7)
ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]

_hasher = PasswordHasher()


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def _secret_for(token_type: TokenType, settings: Settings) -> str:
    if token_type == "access":
        return settings.jwt_secret
    return settings.jwt_refresh_secret


def _create_token(
    subject: str,
    token_type: TokenType,
    ttl: timedelta,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    secret = _secret_for(token_type, settings)
    if not secret:
        raise TokenError(f"missing secret for token type {token_type}")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_access_token(subject: str, settings: Settings | None = None) -> str:
    return _create_token(subject, "access", ACCESS_TTL, settings)


def create_refresh_token(subject: str, settings: Settings | None = None) -> str:
    return _create_token(subject, "refresh", REFRESH_TTL, settings)


def decode_token(
    token: str,
    expected_type: TokenType,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    secret = _secret_for(expected_type, settings)
    if not secret:
        raise TokenError(f"missing secret for token type {expected_type}")
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise TokenError(
            f"unexpected token type: got {payload.get('type')!r}, want {expected_type!r}"
        )
    if not payload.get("sub"):
        raise TokenError("missing subject")
    return payload
