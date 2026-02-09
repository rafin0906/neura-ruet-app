# app/models/result_sheet_models.py
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


class ResultSheet(Base):
    __tablename__ = "result_sheets"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))

    # ✅ teacher-only creator
    created_by_teacher_id = Column(
        String(36),
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String, nullable=True)

    ct_no = Column(Integer, nullable=True)
    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)

    dept = Column(String, nullable=False)
    section = Column(String, nullable=False)
    series = Column(String, nullable=False)

    starting_roll = Column(String, nullable=True)
    ending_roll = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    entries = relationship(
        "ResultEntry",
        back_populates="result_sheet",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ResultEntry.roll_no.asc()",
    )

    created_by_teacher = relationship("Teacher", foreign_keys=[created_by_teacher_id])

    __table_args__ = (
        # ✅ PREVENT duplicate sheet per teacher + course + CT + group
        UniqueConstraint(
            "created_by_teacher_id",
            "dept",
            "section",
            "series",
            "course_code",
            "ct_no",
            name="uq_teacher_course_ct_group",
        ),

        # existing indexes
        Index("ix_result_sheets_dept_section_series", "dept", "section", "series"),
        Index("ix_result_sheets_course_code", "course_code"),
        Index("ix_result_sheets_ct_no", "ct_no"),
    )
