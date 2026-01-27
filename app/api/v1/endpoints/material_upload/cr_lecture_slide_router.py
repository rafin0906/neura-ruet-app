from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.lecture_slide_models import LectureSlide
from app.models.cr_models import CR
from app.services.dependencies import get_current_cr

from app.schemas.backend_schemas.lecture_slide_schemas import (
    CRLectureSlideCreate,
    CRLectureSlideUpdate,
    LectureSlideResponse,
)

from app.services.material_service import (
    get_lecture_slide_or_404,
    ensure_cr_owns_lecture_slide,
)

router = APIRouter(prefix="/crs/materials/lecture-slides", tags=["Lecture Slide Materials"])


@router.post("", response_model=LectureSlideResponse, status_code=status.HTTP_201_CREATED)
def create_lecture_slide(
    payload: CRLectureSlideCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    obj = LectureSlide(
        drive_url=str(payload.drive_url),
        course_code=payload.course_code,  # uppercased by schema validator
        course_name=payload.course_name,
        topic=payload.topic,

        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),

        uploaded_by_cr_id=str(cr.id),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=List[LectureSlideResponse])
def list_lecture_slides(
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    return (
        db.query(LectureSlide)
        .filter(LectureSlide.uploaded_by_cr_id == str(cr.id))
        .filter(LectureSlide.dept == cr.dept)
        .filter(LectureSlide.sec == cr_sec)
        .filter(LectureSlide.series == str(cr.series))
        .order_by(LectureSlide.created_at.desc())
        .all()
    )


@router.get("/{slide_id}", response_model=LectureSlideResponse)
def get_lecture_slide(
    slide_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_lecture_slide_or_404(db, slide_id)
    ensure_cr_owns_lecture_slide(obj, cr.id)
    return obj


@router.patch("/{slide_id}", response_model=LectureSlideResponse)
def update_lecture_slide(
    slide_id: str,
    payload: CRLectureSlideUpdate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_lecture_slide_or_404(db, slide_id)
    ensure_cr_owns_lecture_slide(obj, cr.id)

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


@router.delete("/{slide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lecture_slide(
    slide_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    obj = get_lecture_slide_or_404(db, slide_id)
    ensure_cr_owns_lecture_slide(obj, cr.id)

    db.delete(obj)
    db.commit()
    return None
