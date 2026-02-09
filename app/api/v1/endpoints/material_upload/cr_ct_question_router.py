import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.models.ct_question_models import CTQuestion
from app.models.cr_models import CR
from app.services.dependencies import get_current_cr

from app.schemas.backend_schemas.ct_question_schemas import (
    CRCTQuestionCreate,
    CRCTQuestionUpdate,
    CTQuestionResponse,
)

from app.services.material_service import (
    get_ct_question_or_404,
    ensure_cr_owns_ct_question,
)

from app.ai.embedding_client import embed_texts

router = APIRouter(
    prefix="/crs/materials/ct-questions",
    tags=["CT Question Materials"]
)

logger = logging.getLogger(__name__)

# must match your embedding model
EMBED_DIM = 384


def _build_ct_template(obj: CTQuestion) -> str:
    parts = [
        "material: ct_question",
        f"course_code: {obj.course_code}",
        f"course_name: {obj.course_name}",
        f"ct_no: {obj.ct_no}",
        f"dept: {obj.dept}",
        f"sec: {obj.sec}",
        f"series: {obj.series}",
        f"url: {obj.drive_url}",
    ]
    return " | ".join([p for p in parts if p and "None" not in p])


async def _try_update_ct_embedding(obj: CTQuestion) -> None:
    """
    Regenerate embedding and update obj.vector_embeddings.
    If embedding fails, keep old embedding (do not set None).
    """
    template = _build_ct_template(obj)

    try:
        vecs = await embed_texts([template])

        if not vecs or not isinstance(vecs, (list, tuple)):
            raise ValueError("embed_texts returned empty/non-list")

        emb = vecs[0]

        if not isinstance(emb, (list, tuple)):
            raise TypeError(f"Embedding must be list/tuple, got {type(emb)}")

        if len(emb) != EMBED_DIM:
            raise ValueError(
                f"Embedding dim mismatch: expected {EMBED_DIM}, got {len(emb)}"
            )

        obj.vector_embeddings = [float(x) for x in emb]

    except Exception as e:
        logger.exception("Embedding failed (kept old embedding): %s", e)


@router.post("", response_model=CTQuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_ct_question(
    payload: CRCTQuestionCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    obj = CTQuestion(
        drive_url=str(payload.drive_url),
        course_code=(payload.course_code.upper() if payload.course_code else None),
        course_name=payload.course_name,
        ct_no=payload.ct_no,
        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),
        uploaded_by_cr_id=str(cr.id),
    )

    # generate embedding before saving
    await _try_update_ct_embedding(obj)

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
async def update_ct_question(
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

    # 1) update fields
    for k, v in data.items():
        setattr(obj, k, v)

    # 2) re-embed only if semantic fields changed
    SEMANTIC_FIELDS = {"drive_url", "course_code", "course_name", "ct_no"}
    if any(f in data for f in SEMANTIC_FIELDS):
        await _try_update_ct_embedding(obj)

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
