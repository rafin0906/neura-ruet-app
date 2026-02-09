import logging
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

from app.ai.embedding_client import embed_texts

router = APIRouter(
    prefix="/crs/materials/lecture-slides",
    tags=["Lecture Slide Materials"],
)

logger = logging.getLogger(__name__)

# must match embedding model used in DB
EMBED_DIM = 384


# ----------------------------
# Embedding helpers
# ----------------------------
def _build_slide_template(obj: LectureSlide) -> str:
    parts = [
        "material: lecture_slide",
        f"course_code: {obj.course_code}",
        f"course_name: {obj.course_name}",
        f"topic: {obj.topic}",
        f"dept: {obj.dept}",
        f"sec: {obj.sec}",
        f"series: {obj.series}",
        f"url: {obj.drive_url}",
    ]
    return " | ".join([p for p in parts if p and "None" not in p])


async def _try_update_slide_embedding(obj: LectureSlide) -> None:
    """
    Regenerate embedding and update obj.vector_embeddings.
    If embedding fails, keep existing embedding (do not set None).
    """
    template = _build_slide_template(obj)

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


# ----------------------------
# Routes
# ----------------------------
@router.post(
    "",
    response_model=LectureSlideResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lecture_slide(
    payload: CRLectureSlideCreate,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    cr_sec = getattr(cr, "sec", None) or getattr(cr, "section", None)

    obj = LectureSlide(
        drive_url=str(payload.drive_url),
        course_code=(payload.course_code.upper() if payload.course_code else None),
        course_name=payload.course_name,
        topic=payload.topic,
        dept=cr.dept,
        sec=cr_sec,
        series=str(cr.series),
        uploaded_by_cr_id=str(cr.id),
    )

    # generate embedding before saving
    await _try_update_slide_embedding(obj)

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
async def update_lecture_slide(
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

    # 1) update fields
    for k, v in data.items():
        setattr(obj, k, v)

    # 2) re-embed only if semantic fields changed
    SEMANTIC_FIELDS = {"drive_url", "course_code", "course_name", "topic"}
    if any(f in data for f in SEMANTIC_FIELDS):
        await _try_update_slide_embedding(obj)

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
