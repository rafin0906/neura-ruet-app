import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Enum as SAEnum, Index

from app.db.database import Base


class DeviceOwnerRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    cr = "cr"


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    token = Column(String, nullable=False, unique=True, index=True)

    owner_role = Column(SAEnum(DeviceOwnerRole, name="device_owner_role"), nullable=False)
    owner_id = Column(String(36), nullable=False, index=True)

    platform = Column(String, nullable=False, default="android")

    # Denormalized audience fields for fast targeting.
    dept = Column(String, nullable=True, index=True)
    series = Column(String, nullable=True, index=True)
    sec = Column(String, nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_device_tokens_owner", DeviceToken.owner_role, DeviceToken.owner_id)
