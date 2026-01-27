# app/api/v1/endpoints/material_upload/cr_class_note_router.py
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.models.class_note_models import ClassNote
from app.models.cr_models import CR
from app.services.dependencies import get_current_cr

from app.schemas.backend_schemas.class_note_schemas import (
    CRClassNoteCreate,
    CRClassNoteUpdate,
    ClassNoteResponse,
)

from app.services.material_service import get_class_note_or_404, ensure_cr_owns_note


router = APIRouter(prefix="/crs/materials/class-notes", tags=["Class Note Materials"])


@router.post("", response_model=ClassNoteResponse, status_code=status.HTTP_201_CREATED)
def create_class_note(
    payload: CRClassNoteCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    note = ClassNote(
        drive_url=str(payload.drive_url),
        course_code=payload.course_code,  # uppercased by schema validator
        course_name=payload.course_name,
        topic=payload.topic,
        written_by=payload.written_by,
        # filled from CR, not from payload
        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),
        # ownership
        uploaded_by_cr_id=str(cr.id),
    )

    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("", response_model=List[ClassNoteResponse])
def list_class_notes(
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    query = (
        db.query(ClassNote)
        .filter(ClassNote.uploaded_by_cr_id == str(cr.id))
        .filter(ClassNote.dept == cr.dept)
        .filter(ClassNote.sec == cr_sec)
        .filter(ClassNote.series == str(cr.series))
    )

    return (
        query.order_by(ClassNote.created_at.desc())
        .all()
    )


@router.get("/{note_id}", response_model=ClassNoteResponse)
def get_class_note(
    note_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    note = get_class_note_or_404(db, note_id)
    ensure_cr_owns_note(note, cr.id)  # should check uploaded_by_cr_id
    return note


@router.patch("/{note_id}", response_model=ClassNoteResponse)
def update_class_note(
    note_id: str,
    payload: CRClassNoteUpdate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    note = get_class_note_or_404(db, note_id)
    ensure_cr_owns_note(note, cr.id)

    data = payload.model_dump(exclude_unset=True)

    if "drive_url" in data:
        data["drive_url"] = str(data["drive_url"])

    if "course_code" in data and data["course_code"] is not None:
        data["course_code"] = data["course_code"].upper()

    # ✅ Update only allowed fields (dept/sec/series not present in schema anyway)
    for k, v in data.items():
        setattr(note, k, v)

    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class_note(
    note_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    note = get_class_note_or_404(db, note_id)
    ensure_cr_owns_note(note, cr.id)

    db.delete(note)
    db.commit()
    return None
