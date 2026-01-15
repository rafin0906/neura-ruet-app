import uuid
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.db.database import Base


class Notice(Base):
    __tablename__ = "notices"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )
    notice_message = Column(String, nullable=False)
    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
