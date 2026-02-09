from __future__ import annotations
from fastapi import HTTPException, status

import re
from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, case, literal, or_, cast, String
from sqlalchemy.sql.elements import ColumnElement

from app.models.class_note_models import ClassNote
from app.models.ct_question_models import CTQuestion
from app.models.lecture_slide_models import LectureSlide
from app.models.semester_question_models import SemesterQuestion



def get_class_note_or_404(db: Session, note_id: str) -> ClassNote:
    note = db.query(ClassNote).filter(ClassNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Class note not found")
    return note


def ensure_cr_owns_note(note: ClassNote, cr_id: str):
    if note.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_ct_question_or_404(db: Session, ct_id: str) -> CTQuestion:
    obj = db.query(CTQuestion).filter(CTQuestion.id == ct_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="CT Question not found")
    return obj


def ensure_cr_owns_ct_question(obj: CTQuestion, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_lecture_slide_or_404(db: Session, slide_id: str) -> LectureSlide:
    obj = db.query(LectureSlide).filter(LectureSlide.id == slide_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Lecture slide not found")
    return obj


def ensure_cr_owns_lecture_slide(obj: LectureSlide, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_semester_question_or_404(db: Session, sq_id: str) -> SemesterQuestion:
    obj = db.query(SemesterQuestion).filter(SemesterQuestion.id == sq_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Semester question not found")
    return obj


def ensure_cr_owns_semester_question(obj: SemesterQuestion, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


