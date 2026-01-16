import uuid
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
from app.models.chat_room_models import SenderRole  # reuse the enum


class ResultSheet(Base):
    __tablename__ = "result_sheets"

    id = Column(
        String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4())
    )

    created_by_teacher_id = Column(
        String(36), ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True
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
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    entries = relationship(
        "ResultEntry",
        back_populates="result_sheet",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ResultEntry.roll_no.asc()",
    )

    created_by_teacher = relationship("Teacher", foreign_keys=[created_by_teacher_id])


    __table_args__ = (
        CheckConstraint(
            "created_by_role IN ('teacher','cr')",
            name="ck_resultsheet_creator_role",
        ),
        CheckConstraint(
            "(created_by_role = 'teacher' AND created_by_teacher_id IS NOT NULL AND created_by_cr_id IS NULL) "
            "OR "
            "(created_by_role = 'cr' AND created_by_cr_id IS NOT NULL AND created_by_teacher_id IS NULL)",
            name="ck_resultsheet_creator_fk_matches_role",
        ),
        Index("ix_result_sheets_dept_section_series", "dept", "section", "series"),
        Index("ix_result_sheets_course_code", "course_code"),
    )
