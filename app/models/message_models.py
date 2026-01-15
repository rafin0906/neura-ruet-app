import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    Enum as SAEnum,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.chat_room_models import SenderRole  # shared enum


class Message(Base):
    __tablename__ = "messages"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    chat_room_id = Column(
        String(36), ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False
    )

    sender_role = Column(SAEnum(SenderRole, name="message_sender_role"), nullable=False)

    sender_student_id = Column(
        String(36), ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )
    sender_teacher_id = Column(
        String(36), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
    )
    sender_cr_id = Column(
        String(36), ForeignKey("crs.id", ondelete="SET NULL"), nullable=True
    )

    content = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    chat_room = relationship("ChatRoom", back_populates="messages")
    sender_student = relationship("Student", foreign_keys=[sender_student_id])
    sender_teacher = relationship("Teacher", foreign_keys=[sender_teacher_id])
    sender_cr = relationship("CR", foreign_keys=[sender_cr_id])

    __table_args__ = (
        CheckConstraint(
            "(sender_role = 'assistant' AND sender_student_id IS NULL AND sender_teacher_id IS NULL AND sender_cr_id IS NULL) "
            "OR "
            "(sender_role = 'student' AND sender_student_id IS NOT NULL AND sender_teacher_id IS NULL AND sender_cr_id IS NULL) "
            "OR "
            "(sender_role = 'teacher' AND sender_teacher_id IS NOT NULL AND sender_student_id IS NULL AND sender_cr_id IS NULL) "
            "OR "
            "(sender_role = 'cr' AND sender_cr_id IS NOT NULL AND sender_student_id IS NULL AND sender_teacher_id IS NULL)",
            name="ck_message_sender_role_matches_sender_fk",
        ),
        Index("ix_messages_chat_room_id_created_at", "chat_room_id", "created_at"),
    )
