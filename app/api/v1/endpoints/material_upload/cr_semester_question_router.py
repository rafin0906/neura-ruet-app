from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.semester_question_models import SemesterQuestion
from app.models.cr_models import CR
from app.services.dependencies import get_current_cr

from app.schemas.backend_schemas.semester_question_schemas import (
    CRSemesterQuestionCreate,
    CRSemesterQuestionUpdate,
    SemesterQuestionResponse,
)

from app.services.material_service import (
    get_semester_question_or_404,
    ensure_cr_owns_semester_question,
)

router = APIRouter(prefix="/crs/materials/semester-questions", tags=["Semester Question Materials"])


@router.post("", response_model=SemesterQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_semester_question(
    payload: CRSemesterQuestionCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    obj = SemesterQuestion(
        drive_url=str(payload.drive_url),
        course_code=payload.course_code,  # uppercased by schema validator
        course_name=payload.course_name,
        year=payload.year,

        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),

        uploaded_by_cr_id=str(cr.id),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=List[SemesterQuestionResponse])
def list_semester_questions(
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    return (
        db.query(SemesterQuestion)
        .filter(SemesterQuestion.uploaded_by_cr_id == str(cr.id))
        .filter(SemesterQuestion.dept == cr.dept)
        .filter(SemesterQuestion.sec == cr_sec)
        .filter(SemesterQuestion.series == str(cr.series))
        .order_by(SemesterQuestion.created_at.desc())
        .all()
    )


@router.get("/{sq_id}", response_model=SemesterQuestionResponse)
def get_semester_question(
    sq_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_semester_question_or_404(db, sq_id)
    ensure_cr_owns_semester_question(obj, cr.id)
    return obj


@router.patch("/{sq_id}", response_model=SemesterQuestionResponse)
def update_semester_question(
    sq_id: str,
    payload: CRSemesterQuestionUpdate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_semester_question_or_404(db, sq_id)
    ensure_cr_owns_semester_question(obj, cr.id)

    data = payload.model_dump(exclude_unset=True)

    if "drive_url" in data:
        data["drive_url"] = str(data["drive_url"])

    if "course_code" in data and data["course_code"] is not None:
        data["course_code"] = data["course_code"].upper()

    for k, v in data.items():
        setattr(obj, k, v)

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{sq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester_question(
    sq_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_semester_question_or_404(db, sq_id)
    ensure_cr_owns_semester_question(obj, cr.id)

    db.delete(obj)
    db.commit()
    return None
