import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, CheckConstraint, Text, Enum as SAEnum
from sqlalchemy.orm import relationship

from app.db.database import Base


class SenderRole(str, enum.Enum):
    teacher = "teacher"
    cr = "cr"


class Notice(Base):
    __tablename__ = "notices"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    title = Column(String, nullable=False)
    notice_message = Column(Text, nullable=False)

    created_by_role = Column(SAEnum(SenderRole, name="notice_sender_role"), nullable=False)

    created_by_teacher_id = Column(String(36), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    created_by_cr_id = Column(String(36), ForeignKey("crs.id", ondelete="SET NULL"), nullable=True)

    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher = relationship("Teacher", backref="notices", foreign_keys=[created_by_teacher_id])
    cr = relationship("CR", backref="notices", foreign_keys=[created_by_cr_id])

    __table_args__ = (
        CheckConstraint(
            "(created_by_role = 'teacher' AND created_by_teacher_id IS NOT NULL AND created_by_cr_id IS NULL) OR "
            "(created_by_role = 'cr' AND created_by_cr_id IS NOT NULL AND created_by_teacher_id IS NULL)",
            name="ck_notice_created_by_exactly_one",
        ),
    )
