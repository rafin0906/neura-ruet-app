from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy import or_

from app.models.notice_models import Notice
from app.schemas.backend_schemas.notice_schemas import (
    TeacherNoticeCreate,
    CRNoticeCreate,
    TeacherNoticeUpdate,
    CRNoticeUpdate,
)
from app.models.teacher_models import Teacher
from app.models.cr_models import CR
from app.models.student_models import Student

from app.ai.embedding_client import embed_texts

import logging
import asyncio

logger = logging.getLogger(__name__)

# -------------------------
# CREATE
# -------------------------
def create_notice_by_teacher(db: Session, payload: TeacherNoticeCreate, teacher: Teacher) -> Notice:
    notice = Notice(
        title=payload.title.strip(),
        notice_message=payload.notice_message.strip(),
        created_by_role="teacher",
        created_by_teacher_id=str(teacher.id),
        created_by_cr_id=None,
        dept=str(payload.dept),
        sec=payload.sec,
        series=str(payload.series),
    )

    # ✅ generate embeddings (do not fail upload if embedding fails)
    try:
        teacher_name = getattr(teacher, "full_name", "") or getattr(teacher, "name", "")
        template = (
            f"Class/Dept Notice posted by Teacher {teacher_name}. "
            f"Notice audience: dept {notice.dept}, section {notice.sec}, series {notice.series}. "
            f"Title: {notice.title}. "
            f"Message: {notice.notice_message}."
        )
        emb = asyncio.run(embed_texts([template]))[0]
        notice.vector_embeddings = emb
    except Exception:
        logger.exception("Embedding generation failed")
        notice.vector_embeddings = None

    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice



def create_notice_by_cr(db: Session, payload: CRNoticeCreate, cr: CR) -> Notice:
    dept = getattr(cr, "dept", None)
    sec = getattr(cr, "section", None) or getattr(cr, "sec", None)
    series = getattr(cr, "series", None)

    if not (dept and series):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CR profile missing dept/series",
        )

    # Normalize section: treat "None" string as NULL; otherwise keep A/B/C.
    if isinstance(sec, str):
        cleaned = sec.strip()
        if cleaned == "" or cleaned.lower() in {"none", "null"}:
            sec = None
        else:
            sec_upper = cleaned.upper()
            if sec_upper in {"A", "B", "C"}:
                sec = sec_upper
            else:
                # Unknown section in CR profile -> treat as no section
                sec = None

    notice = Notice(
        title=payload.title.strip(),
        notice_message=payload.notice_message.strip(),
        created_by_role="cr",
        created_by_cr_id=str(cr.id),
        created_by_teacher_id=None,
        dept=str(dept),
        sec=sec,
        series=str(series),
    )

    # ✅ generate embeddings (do not fail upload if embedding fails)
    try:
        cr_name = getattr(cr, "full_name", "") or getattr(cr, "name", "")
        cr_roll = str(getattr(cr, "roll_no", "") or getattr(cr, "roll", ""))
        template = (
            f"Class/Dept Notice posted by CR {cr_name} (roll {cr_roll}). "
            f"CR profile: dept {notice.dept}, section {notice.sec}, series {notice.series}. "
            f"Title: {notice.title}. "
            f"Message: {notice.notice_message}."
        )

        logger.info("Embedding template (teacher create): %s", template)
        emb = asyncio.run(embed_texts([template]))[0]
        notice.vector_embeddings = emb
    except Exception:
        notice.vector_embeddings = None

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

    if not (dept and series):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile missing dept/series",
        )

    sec_norm = None
    if isinstance(sec, str):
        cleaned = sec.strip()
        if cleaned != "" and cleaned.lower() not in {"none", "null"}:
            sec_upper = cleaned.upper()
            sec_norm = sec_upper if sec_upper in {"A", "B", "C"} else None

    return (
        db.query(Notice)
        .filter(
            Notice.dept == str(dept),
            Notice.series == str(series),
            or_(Notice.sec == sec_norm, Notice.sec.is_(None)),
        )
        .order_by(desc(Notice.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )


# -------------------------
# CR FEED (teacher notices by dept/sec/series)
# -------------------------
def get_cr_feed_teacher_notices(db: Session, cr: CR, skip: int = 0, limit: int = 50) -> list[Notice]:
    dept = getattr(cr, "dept", None)
    sec = getattr(cr, "section", None) or getattr(cr, "sec", None)
    series = getattr(cr, "series", None)

    if not (dept and series):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CR profile missing dept/series",
        )

    sec_norm = None
    if isinstance(sec, str):
        cleaned = sec.strip()
        if cleaned != "" and cleaned.lower() not in {"none", "null"}:
            sec_upper = cleaned.upper()
            sec_norm = sec_upper if sec_upper in {"A", "B", "C"} else None

    return (
        db.query(Notice)
        .filter(
            Notice.created_by_role == "teacher",
            Notice.dept == str(dept),
            Notice.series == str(series),
            or_(Notice.sec == sec_norm, Notice.sec.is_(None)),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    updated = False

    if payload.title is not None:
        notice.title = payload.title.strip()
        updated = True

    if payload.notice_message is not None:
        notice.notice_message = payload.notice_message.strip()
        updated = True

    # ✅ re-generate embeddings only if something changed
    if updated:
        try:
            cr_name = getattr(cr, "full_name", "") or getattr(cr, "name", "")
            cr_roll = str(getattr(cr, "roll_no", "") or getattr(cr, "roll", ""))
            template = (
                f"Class/Dept Notice posted by CR {cr_name} (roll {cr_roll}). "
                f"CR profile: dept {notice.dept}, section {notice.sec}, series {notice.series}. "
                f"Title: {notice.title}. "
                f"Message: {notice.notice_message}."
            )
            emb = asyncio.run(embed_texts([template]))[0]
            notice.vector_embeddings = emb
        except Exception:
            pass

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

    updated = False

    if payload.title is not None:
        notice.title = payload.title.strip()
        updated = True

    if payload.notice_message is not None:
        notice.notice_message = payload.notice_message.strip()
        updated = True

    # Allow explicit null updates: payload.model_fields_set tracks which fields were provided.
    fields_set = getattr(payload, "model_fields_set", set())

    if "dept" in fields_set:
        notice.dept = str(payload.dept) if payload.dept is not None else notice.dept
        updated = True

    if "sec" in fields_set:
        # payload.sec is already normalized by schema validator (None / A / B / C)
        notice.sec = payload.sec
        updated = True

    if "series" in fields_set:
        notice.series = str(payload.series) if payload.series is not None else notice.series
        updated = True

    # ✅ re-generate embeddings only if something changed
    if updated:
        try:
            teacher_name = getattr(teacher, "full_name", "") or getattr(teacher, "name", "")
            template = (
                f"Class/Dept Notice posted by Teacher {teacher_name}. "
                f"Notice audience: dept {notice.dept}, section {notice.sec}, series {notice.series}. "
                f"Title: {notice.title}. "
                f"Message: {notice.notice_message}."
            )
            emb = asyncio.run(embed_texts([template]))[0]
            notice.vector_embeddings = emb
        except Exception:
            pass

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
