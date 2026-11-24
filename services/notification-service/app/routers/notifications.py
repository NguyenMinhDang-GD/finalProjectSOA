from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import NotificationLog
from app.schemas import NotificationLogResponse
from app.security import require_roles

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("/logs", response_model=list[NotificationLogResponse])
async def list_notification_logs(
    _: dict = Depends(require_roles("STAFF", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(100))
    return [NotificationLogResponse.model_validate(r) for r in rows.all()]
