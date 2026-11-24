from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models import User
from app.schemas import (
    AuthTokenResponse,
    CreateUserByAdminRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.security import create_access_token, hash_password, verify_password
from app.metrics import AUTH_EVENTS_TOTAL


async def seed_default_users(db: AsyncSession) -> None:
    defaults = [
        ("admin@pickleball.vn", "Admin@123", "Quản trị viên Sân", "0901000001", "ADMIN"),
        ("staff@pickleball.vn", "Staff@123", "Nhân viên Quét vé", "0901000002", "STAFF"),
        ("khachhang@pickleball.vn", "Customer@123", "Nguyễn Minh Đăng", "0901000003", "CUSTOMER"),
    ]
    for email, raw_pw, full_name, phone, role in defaults:
        existing = await db.scalar(select(User).where(User.email == email))
        if not existing:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(raw_pw),
                    full_name=full_name,
                    phone=phone,
                    role=role,
                )
            )
    await db.commit()


async def register_customer(db: AsyncSession, data: RegisterRequest) -> AuthTokenResponse:
    normalized_email = data.email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        AUTH_EVENTS_TOTAL.labels(event="register", status="duplicate").inc()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được đăng ký")

    user = User(
        email=normalized_email,
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
        phone=data.phone.strip(),
        role="CUSTOMER",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token, expires_in = create_access_token(str(user.id), user.email, user.role, user.full_name)
    AUTH_EVENTS_TOTAL.labels(event="register", status="success").inc()
    return AuthTokenResponse(access_token=token, expires_in=expires_in, user=UserResponse.model_validate(user))


async def login_user(db: AsyncSession, data: LoginRequest) -> AuthTokenResponse:
    normalized_email = data.email.strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(data.password, user.password_hash):
        AUTH_EVENTS_TOTAL.labels(event="login", status="failed").inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
    if not user.is_active:
        AUTH_EVENTS_TOTAL.labels(event="login", status="inactive").inc()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")

    token, expires_in = create_access_token(str(user.id), user.email, user.role, user.full_name)
    AUTH_EVENTS_TOTAL.labels(event="login", status="success").inc()
    return AuthTokenResponse(access_token=token, expires_in=expires_in, user=UserResponse.model_validate(user))


async def create_user_by_admin(db: AsyncSession, data: CreateUserByAdminRequest) -> UserResponse:
    normalized_email = data.email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")

    user = User(
        email=normalized_email,
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
        phone=data.phone.strip(),
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)
