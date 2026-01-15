import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class ResultEntry(Base):
    __tablename__ = "result_entries"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    result_sheet_id = Column(
        String(36), ForeignKey("result_sheets.id", ondelete="CASCADE"), nullable=False
    )

    roll_no = Column(String, nullable=False)
    marks = Column(String, nullable=False)  # keep String (A+, absent, etc.)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    result_sheet = relationship("ResultSheet", back_populates="entries")

    __table_args__ = (
        UniqueConstraint(
            "result_sheet_id", "roll_no", name="uq_result_entries_sheet_roll"
        ),
        Index("ix_result_entries_sheet_roll", "result_sheet_id", "roll_no"),
    )
