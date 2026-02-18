from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.backend_schemas.push_schemas import DeviceTokenRegister, DeviceTokenRegisterResponse
from app.services.dependencies import get_current_actor
from app.models.device_token_models import DeviceOwnerRole
from app.services.device_token_service import upsert_device_token


router = APIRouter(prefix="/push", tags=["Push"])


@router.post("/device-token", response_model=DeviceTokenRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_device_token(
    payload: DeviceTokenRegister,
    actor=Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    role = actor["role"]
    user = actor["user"]

    dept = getattr(user, "dept", None)
    series = getattr(user, "series", None)
    sec = getattr(user, "section", None) or getattr(user, "sec", None)

    upsert_device_token(
        db,
        token=payload.token,
        owner_role=DeviceOwnerRole(role),
        owner_id=str(getattr(user, "id")),
        platform="android",
        dept=str(dept) if dept is not None else None,
        series=str(series) if series is not None else None,
        sec=str(sec) if sec is not None else None,
    )

    return DeviceTokenRegisterResponse(ok=True)
