"""JWT authentication utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

# --- AUTH TESTING BYPASS FLAG ---
# Set AUTH_DISABLED = False to restore JWT verification and role requirements.
AUTH_DISABLED = True

MOCK_USER = {"user_id": "test_user_id", "role": "admin"}


def verify_password(plain: str, hashed: str) -> bool:
    if AUTH_DISABLED:
        return True
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict[str, Any]:
    if AUTH_DISABLED:
        return MOCK_USER

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        return {"user_id": user_id, "role": payload.get("role", "caller")}
    except JWTError:
        raise credentials_exc


def require_role(*roles: str):
    async def checker(current_user: dict = Depends(get_current_user)):
        if AUTH_DISABLED:
            return current_user
        if current_user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return checker
