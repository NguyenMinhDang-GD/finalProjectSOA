import hmac
from typing import Any
import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


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


def is_valid_internal_key(x_internal_key: str | None) -> bool:
    return bool(
        settings.internal_api_key
        and x_internal_key
        and hmac.compare_digest(x_internal_key, settings.internal_api_key)
    )


def verify_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    if not is_valid_internal_key(x_internal_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Internal key không hợp lệ")


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


async def authorize_booking_access(
    booking_code: str,
    claims: dict[str, Any] | None,
    guest_token: str | None,
) -> dict[str, Any]:
    url = f"{settings.booking_service_url}/api/bookings/internal/{booking_code.strip()}/authorize"
    payload = {
        "user_id": claims.get("sub") if claims else None,
        "role": claims.get("role") if claims else None,
        "guest_token": guest_token,
        "require_owner": False,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"X-Internal-Key": settings.internal_api_key},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể xác thực quyền truy cập đơn đặt sân",
        ) from exc

    if resp.status_code == 404:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đơn đặt sân")
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Lỗi xác thực quyền truy cập đơn đặt sân",
        )

    data = resp.json()
    if not data.get("authorized"):
        reason = data.get("reason") or "Không có quyền truy cập giao dịch thanh toán này"
        if not claims and not guest_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=reason)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
    return data
