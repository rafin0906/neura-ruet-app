import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    UniqueConstraint,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import relationship

from app.db.database import Base


class CTQuestion(Base):
    __tablename__ = "ct_questions"

    id = Column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    drive_url = Column(String, nullable=False)

    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)

    ct_no = Column(Integer, nullable=False)  # ✅ CT number

    dept = Column(String, nullable=False)
    sec = Column(String, nullable=True)
    series = Column(String, nullable=False)

    uploaded_by_cr_id = Column(
        String(36),
        ForeignKey("crs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uploaded_by_cr = relationship(
        "CR",
        foreign_keys=[uploaded_by_cr_id],
        passive_deletes=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # vector embeddings for semantic search (pgvector)
    vector_embeddings = Column(Vector(384), nullable=True)

    __table_args__ = (
        # ✅ prevent duplicates for same target group + course + ct_no
        UniqueConstraint(
            "course_code",
            "dept",
            "sec",
            "series",
            "ct_no",
            name="uq_ct_questions_course_group_ctno",
        ),
        Index("ix_ct_questions_uploaded_by_cr_id", "uploaded_by_cr_id"),
        Index("ix_ct_questions_course_code", "course_code"),
        Index("ix_ct_questions_dept_sec_series", "dept", "sec", "series"),
    )
