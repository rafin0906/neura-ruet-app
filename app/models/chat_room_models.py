import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class SenderRole(str, enum.Enum):
    assistant = "assistant"
    student = "student"
    teacher = "teacher"
    cr = "cr"


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    owner_role = Column(SAEnum(SenderRole, name="chat_owner_role"), nullable=False)

    owner_student_id = Column(
        String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    owner_teacher_id = Column(
        String(36), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    owner_cr_id = Column(
        String(36), ForeignKey("crs.id", ondelete="SET NULL"), nullable=True
    )

    title = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    messages = relationship(
        "Message",
        back_populates="chat_room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.created_at.asc()",
    )

    owner_student = relationship("Student", foreign_keys=[owner_student_id])
    owner_teacher = relationship("Teacher", foreign_keys=[owner_teacher_id])
    owner_cr = relationship("CR", foreign_keys=[owner_cr_id])

    __table_args__ = (
        CheckConstraint(
            "owner_role IN ('student','teacher','cr')",
            name="ck_chatroom_owner_role_not_assistant",
        ),
        CheckConstraint(
            "(CASE WHEN owner_student_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN owner_teacher_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN owner_cr_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_chatroom_exactly_one_owner_fk",
        ),
        Index("ix_chat_rooms_owner_student_id", "owner_student_id"),
        Index("ix_chat_rooms_owner_teacher_id", "owner_teacher_id"),
        Index("ix_chat_rooms_owner_cr_id", "owner_cr_id"),
    )
