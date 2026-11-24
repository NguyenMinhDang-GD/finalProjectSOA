import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas import (
    AuthTokenResponse,
    CreateUserByAdminRequest,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.security import get_current_claims, require_roles
from app.services.auth_service import create_user_by_admin, login_user, register_customer

router = APIRouter(prefix="/api/auth", tags=["Authentication & Users"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register_customer(db, payload)


@router.post("/login", response_model=AuthTokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login_user(db, payload)


@router.get("/me", response_model=UserResponse)
async def get_me(claims: dict = Depends(get_current_claims), db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.id == uuid.UUID(claims["sub"])))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")
    return UserResponse.model_validate(user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(select(User).order_by(User.created_at.desc()))
    return [UserResponse.model_validate(u) for u in result.all()]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserByAdminRequest,
    _: dict = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await create_user_by_admin(db, payload)
