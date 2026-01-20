from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.ct_question_models import CTQuestion
from app.models.cr_models import CR
from app.services.dependencies import get_current_cr

from app.schemas.ct_question_schemas import (
    CRCTQuestionCreate,
    CRCTQuestionUpdate,
    CTQuestionResponse,
)

from app.services.material_service import (
    get_ct_question_or_404,
    ensure_cr_owns_ct_question,
)

router = APIRouter(prefix="/crs/materials/ct-questions", tags=["CT Question Materials"])


@router.post("", response_model=CTQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_ct_question(
    payload: CRCTQuestionCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    obj = CTQuestion(
        drive_url=str(payload.drive_url),
        course_code=payload.course_code,  # uppercased by schema validator
        course_name=payload.course_name,
        ct_no=payload.ct_no,

        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),

        uploaded_by_cr_id=str(cr.id),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=List[CTQuestionResponse])
def list_ct_questions(
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    return (
        db.query(CTQuestion)
        .filter(CTQuestion.uploaded_by_cr_id == str(cr.id))
        .filter(CTQuestion.dept == cr.dept)
        .filter(CTQuestion.sec == cr_sec)
        .filter(CTQuestion.series == str(cr.series))
        .order_by(CTQuestion.created_at.desc())
        .all()
    )


@router.get("/{ct_id}", response_model=CTQuestionResponse)
def get_ct_question(
    ct_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_ct_question_or_404(db, ct_id)
    ensure_cr_owns_ct_question(obj, cr.id)
    return obj


@router.patch("/{ct_id}", response_model=CTQuestionResponse)
def update_ct_question(
    ct_id: str,
    payload: CRCTQuestionUpdate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_ct_question_or_404(db, ct_id)
    ensure_cr_owns_ct_question(obj, cr.id)

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


@router.delete("/{ct_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ct_question(
    ct_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_ct_question_or_404(db, ct_id)
    ensure_cr_owns_ct_question(obj, cr.id)

    db.delete(obj)
    db.commit()
    return None
