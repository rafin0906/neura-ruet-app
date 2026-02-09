# app/models/class_note_models.py
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Index

from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship

from app.db.database import Base


class ClassNote(Base):
    __tablename__ = "class_notes"

    id = Column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    drive_url = Column(String, nullable=False)  # google drive link

    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    written_by = Column(String, nullable=False)

    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
    series = Column(String, nullable=False)

    # ✅ REAL FK (same pattern as ChatRoom.owner_cr_id)
    uploaded_by_cr_id = Column(
        String(36),
        ForeignKey("crs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ✅ ORM relationship
    uploaded_by_cr = relationship(
        "CR",
        foreign_keys=[uploaded_by_cr_id],
        passive_deletes=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # vector embeddings for semantic search (pgvector)
    vector_embeddings = Column(Vector(384), nullable=True)

    __table_args__ = (Index("ix_class_notes_uploaded_by_cr_id", "uploaded_by_cr_id"),)
