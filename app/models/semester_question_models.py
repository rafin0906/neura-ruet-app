import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class SemesterQuestion(Base):
    __tablename__ = "semester_questions"

    id = Column(
        String(36),
        primary_key=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    drive_url = Column(String, nullable=False)

    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)

    year = Column(Integer, nullable=False)  # ✅ exam year (e.g., 2021)

    dept = Column(String, nullable=False)
    sec = Column(String, nullable=False)
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

    __table_args__ = (
        # ✅ prevent duplicates for same target group + course + year
        UniqueConstraint(
            "course_code", "dept", "sec", "series", "year",
            name="uq_semester_questions_course_group_year"
        ),
        Index("ix_semester_questions_uploaded_by_cr_id", "uploaded_by_cr_id"),
        Index("ix_semester_questions_course_code", "course_code"),
        Index("ix_semester_questions_dept_sec_series", "dept", "sec", "series"),
        Index("ix_semester_questions_year", "year"),
    )
