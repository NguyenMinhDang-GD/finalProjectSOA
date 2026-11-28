from datetime import datetime, timedelta, timezone
import hmac
from typing import Any
import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    salt = bcrypt.gensalt(rounds=10)
    return bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(raw_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(raw_password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, email: str, role: str, full_name: str) -> tuple[str, int]:
    expires_seconds = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "full_name": full_name,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_seconds)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_seconds


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token đã hết hạn") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ") from exc


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thiếu token xác thực")
    return decode_token(credentials.credentials)


def require_roles(*allowed_roles: str):
    async def _dependency(claims: dict[str, Any] = Depends(get_current_claims)) -> dict[str, Any]:
        if claims.get("role") not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập chức năng này")
        return claims

    return _dependency


async def verify_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    if (
        not settings.internal_api_key
        or not x_internal_key
        or not hmac.compare_digest(x_internal_key, settings.internal_api_key)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal service key")
