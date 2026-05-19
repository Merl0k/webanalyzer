"""
JWT access + refresh token helpers.
"""
import os
import jwt
from datetime import datetime, timedelta, timezone

SECRET      = os.getenv("JWT_SECRET", "change-me-in-production-please")
ALG         = "HS256"
ACCESS_EXP  = int(os.getenv("JWT_ACCESS_MINUTES", "60"))
REFRESH_EXP = int(os.getenv("JWT_REFRESH_DAYS", "30"))


def make_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "type": "access",
         "iat": now, "exp": now + timedelta(minutes=ACCESS_EXP)},
        SECRET, algorithm=ALG,
    )


def make_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "type": "refresh",
         "iat": now, "exp": now + timedelta(days=REFRESH_EXP)},
        SECRET, algorithm=ALG,
    )


def decode_token(token: str) -> dict:
    """Returns payload dict or raises jwt.PyJWTError."""
    return jwt.decode(token, SECRET, algorithms=[ALG])
