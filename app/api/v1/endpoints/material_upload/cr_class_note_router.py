# app/api/v1/endpoints/material_upload/cr_class_note_router.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
import logging

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
from app.ai.embedding_client import embed_texts


router = APIRouter(prefix="/crs/materials/class-notes", tags=["Class Note Materials"])

logger = logging.getLogger(__name__)

# set this to the dimension you're actually using in DB/model
EMBED_DIM = 384


# ----------------------------
# Embedding helpers
# ----------------------------
def _build_classnote_template(note: ClassNote) -> str:
    # keep it consistent + embedding-friendly
    parts = [
        f"material: class_note",
        f"course_code: {note.course_code}",
        f"course_name: {note.course_name}",
        f"topic: {note.topic}",
        f"written_by: {note.written_by}",
        f"dept: {note.dept}",
        f"sec: {note.sec}",
        f"series: {note.series}",
        f"url: {note.drive_url}",
    ]
    return " | ".join([p for p in parts if p and "None" not in p])


async def _try_update_classnote_embedding(note: ClassNote) -> None:
    """
    Regenerate embedding and update note.vector_embeddings.
    If embedding fails, keep existing embedding (do not set None).
    """
    template = _build_classnote_template(note)

    try:
        vecs = await embed_texts([template])
        if not vecs or not isinstance(vecs, (list, tuple)):
            raise ValueError("embed_texts returned empty/non-list")

        emb = vecs[0]

        if not isinstance(emb, (list, tuple)):
            raise TypeError(f"Embedding must be list/tuple, got {type(emb)}")

        if len(emb) != EMBED_DIM:
            raise ValueError(f"Embedding dim mismatch: expected {EMBED_DIM}, got {len(emb)}")

        note.vector_embeddings = [float(x) for x in emb]

    except Exception as e:
        logger.exception("Embedding failed (kept old embedding): %s", e)


# ----------------------------
# Routes
# ----------------------------
@router.post("", response_model=ClassNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_class_note(
    payload: CRClassNoteCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    note = ClassNote(
        drive_url=str(payload.drive_url),
        course_code=(payload.course_code.upper() if payload.course_code else None),
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

    # generate embedding before saving
    await _try_update_classnote_embedding(note)

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

    notes = (
        db.query(ClassNote)
        .filter(ClassNote.uploaded_by_cr_id == str(cr.id))
        .filter(ClassNote.dept == cr.dept)
        .filter(ClassNote.sec == cr_sec)
        .filter(ClassNote.series == str(cr.series))
        .order_by(ClassNote.created_at.desc())
        .all()
    )
    return notes


@router.get("/{note_id}", response_model=ClassNoteResponse)
def get_class_note(
    note_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    note = get_class_note_or_404(db, note_id)
    ensure_cr_owns_note(note, cr.id)
    return note


@router.patch("/{note_id}", response_model=ClassNoteResponse)
async def update_class_note(
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

    # 1) update fields
    for k, v in data.items():
        setattr(note, k, v)

    # 2) re-embed only if semantic fields changed
    SEMANTIC_FIELDS = {"drive_url", "course_code", "course_name", "topic", "written_by"}
    if any(f in data for f in SEMANTIC_FIELDS):
        await _try_update_classnote_embedding(note)

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
