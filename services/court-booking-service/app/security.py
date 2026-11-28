import hashlib
import hmac
from typing import Any
import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def hash_guest_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_guest_token(raw_token: str | None, stored_hash: str | None) -> bool:
    if not raw_token or not stored_hash:
        return False
    candidate = hash_guest_token(raw_token.strip())
    return hmac.compare_digest(candidate, stored_hash)


def _decode(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token đã hết hạn") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ") from exc


async def verify_user_active(claims: dict[str, Any]) -> None:
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token thiếu thông tin người dùng")
    url = f"{settings.auth_service_url}/api/auth/internal/users/{user_id}/status"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url, headers={"X-Internal-Key": settings.internal_api_key})
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể xác thực trạng thái tài khoản",
        ) from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không tồn tại")
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lỗi xác thực trạng thái tài khoản",
        )
    data = resp.json()
    if not data.get("is_active"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")


async def get_optional_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    claims = _decode(credentials.credentials)
    await verify_user_active(claims)
    return claims


async def get_current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thiếu token xác thực")
    claims = _decode(credentials.credentials)
    await verify_user_active(claims)
    return claims


def require_roles(*allowed_roles: str):
    async def _dep(claims: dict[str, Any] = Depends(get_current_claims)) -> dict[str, Any]:
        if claims.get("role") not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không đủ quyền truy cập")
        return claims

    return _dep


async def verify_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    if (
        not settings.internal_api_key
        or not x_internal_key
        or not hmac.compare_digest(x_internal_key, settings.internal_api_key)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal service key")
