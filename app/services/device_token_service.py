from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models.device_token_models import DeviceToken, DeviceOwnerRole


def _ensure_device_tokens_table(db: Session) -> None:
    """Best-effort safety net for dev/test environments.

    If Alembic migrations haven't been applied yet, queries against DeviceToken
    will fail with a ProgrammingError (missing table / missing enum type).
    Creating the table here unblocks token registration so pushes can work.
    """

    bind = db.get_bind()
    if bind is None:
        return
    DeviceToken.__table__.create(bind=bind, checkfirst=True)


def _normalize_section(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned == "" or cleaned.lower() in {"none", "null"}:
        return None
    upper = cleaned.upper()
    return upper if upper in {"A", "B", "C"} else None


def upsert_device_token(
    db: Session,
    *,
    token: str,
    owner_role: DeviceOwnerRole,
    owner_id: str,
    platform: str,
    dept: str | None,
    series: str | None,
    sec: str | None,
) -> DeviceToken:
    token_clean = token.strip()

    try:
        row = db.query(DeviceToken).filter(DeviceToken.token == token_clean).first()
    except ProgrammingError:
        # Most commonly: device_tokens table doesn't exist (migration not applied).
        db.rollback()
        _ensure_device_tokens_table(db)
        row = db.query(DeviceToken).filter(DeviceToken.token == token_clean).first()
    if row:
        row.owner_role = owner_role
        row.owner_id = owner_id
        row.platform = platform
        row.dept = str(dept) if dept is not None else None
        row.series = str(series) if series is not None else None
        row.sec = _normalize_section(sec)
        row.is_active = True
        row.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return row

    row = DeviceToken(
        token=token_clean,
        owner_role=owner_role,
        owner_id=str(owner_id),
        platform=str(platform).strip().lower() if platform else "android",
        dept=str(dept) if dept is not None else None,
        series=str(series) if series is not None else None,
        sec=_normalize_section(sec),
        is_active=True,
        last_seen_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def deactivate_token(db: Session, token: str) -> None:
    try:
        row = db.query(DeviceToken).filter(DeviceToken.token == token).first()
    except ProgrammingError:
        db.rollback()
        _ensure_device_tokens_table(db)
        row = db.query(DeviceToken).filter(DeviceToken.token == token).first()
    if not row:
        return
    row.is_active = False
    db.commit()
