from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.notice_models import Notice
from app.schemas.notice_schemas import TeacherNoticeCreate, CRNoticeCreate, TeacherNoticeUpdate, CRNoticeUpdate
from app.models.teacher_models import Teacher
from app.models.cr_models import CR
from app.models.student_models import Student


# -------------------------
# CREATE
# -------------------------
def create_notice_by_teacher(db: Session, payload: TeacherNoticeCreate, teacher: Teacher) -> Notice:
    notice = Notice(
        title=payload.title,
        notice_message=payload.notice_message,
        created_by_role="teacher",
        created_by_teacher_id=str(teacher.id),
        created_by_cr_id=None,
        dept=payload.dept,
        sec=payload.sec,
        series=str(payload.series),
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


def create_notice_by_cr(db: Session, payload: CRNoticeCreate, cr: CR) -> Notice:
    dept = getattr(cr, "dept", None)
    sec = getattr(cr, "section", None) or getattr(cr, "sec", None)
    series = getattr(cr, "series", None)

    if not (dept and sec and series):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CR profile missing dept/sec/series",
        )

    notice = Notice(
        title=payload.title,
        notice_message=payload.notice_message,
        created_by_role="cr",
        created_by_cr_id=str(cr.id),
        created_by_teacher_id=None,
        dept=str(dept),
        sec=str(sec),
        series=str(series),
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


# -------------------------
# CR: GET ALL + GET BY ID (own)
# -------------------------
def get_cr_notices(db: Session, cr: CR, skip: int = 0, limit: int = 50) -> list[Notice]:
    return (
        db.query(Notice)
        .filter(Notice.created_by_cr_id == str(cr.id))
        .order_by(desc(Notice.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_cr_notice_by_id(db: Session, cr: CR, notice_id: str) -> Notice:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_cr_id == str(cr.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return notice


# -------------------------
# TEACHER: GET ALL + GET BY ID (own)
# -------------------------
def get_teacher_notices(db: Session, teacher: Teacher, skip: int = 0, limit: int = 50) -> list[Notice]:
    return (
        db.query(Notice)
        .filter(Notice.created_by_teacher_id == str(teacher.id))
        .order_by(desc(Notice.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_teacher_notice_by_id(db: Session, teacher: Teacher, notice_id: str) -> Notice:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_teacher_id == str(teacher.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return notice


# -------------------------
# STUDENT FEED (by dept/sec/series)
# -------------------------
def get_student_notices(db: Session, student: Student, skip: int = 0, limit: int = 50) -> list[Notice]:
    dept = getattr(student, "dept", None)
    sec = getattr(student, "section", None) or getattr(student, "sec", None)
    series = getattr(student, "series", None)

    if not (dept and sec and series):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile missing dept/sec/series",
        )

    return (
        db.query(Notice)
        .filter(
            Notice.dept == str(dept),
            Notice.sec == str(sec),
            Notice.series == str(series),
        )
        .order_by(desc(Notice.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


# -------------------------
# CR: UPDATE + DELETE (own)
# -------------------------
def update_cr_notice(db: Session, cr: CR, notice_id: str, payload: CRNoticeUpdate) -> Notice:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_cr_id == str(cr.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    if payload.title is not None:
        notice.title = payload.title
    if payload.notice_message is not None:
        notice.notice_message = payload.notice_message

    db.commit()
    db.refresh(notice)
    return notice


def delete_cr_notice(db: Session, cr: CR, notice_id: str) -> None:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_cr_id == str(cr.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    db.delete(notice)
    db.commit()


# -------------------------
# TEACHER: UPDATE + DELETE (own)
# -------------------------
def update_teacher_notice(db: Session, teacher: Teacher, notice_id: str, payload: TeacherNoticeUpdate) -> Notice:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_teacher_id == str(teacher.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    if payload.title is not None:
        notice.title = payload.title
    if payload.notice_message is not None:
        notice.notice_message = payload.notice_message

    # Teacher can change targeting (optional fields)
    if payload.dept is not None:
        notice.dept = payload.dept
    if payload.sec is not None:
        notice.sec = payload.sec
    if payload.series is not None:
        notice.series = str(payload.series)

    db.commit()
    db.refresh(notice)
    return notice


def delete_teacher_notice(db: Session, teacher: Teacher, notice_id: str) -> None:
    notice = (
        db.query(Notice)
        .filter(Notice.id == notice_id, Notice.created_by_teacher_id == str(teacher.id))
        .first()
    )
    if not notice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")

    db.delete(notice)
    db.commit()
