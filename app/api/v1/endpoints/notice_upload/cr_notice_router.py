from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.backend_schemas.notice_schemas import (
    CRNoticeCreate,
    NoticeResponse,
    CRNoticeUpdate,
)
from app.services.dependencies import get_current_cr
from app.services.notice_service import (
    create_notice_by_cr,
    get_cr_notices,
    get_cr_notice_by_id,
    get_cr_feed_teacher_notices,
    update_cr_notice,
    delete_cr_notice,
)
from app.models.cr_models import CR
from app.services.push_notification_service import send_notice_push_by_id

router = APIRouter(prefix="/cr/notices", tags=["Notices (CR)"])


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def upload_notice_cr(
    payload: CRNoticeCreate,
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """
    Creates a notice by CR.

    Handled inside service:
    - dept/sec/series resolved from CR profile
    - created_by_role = "cr"
    - vector embeddings generated and stored
    """
    notice = create_notice_by_cr(db=db, payload=payload, cr=cr)
    background_tasks.add_task(send_notice_push_by_id, str(notice.id))
    return notice


@router.get("", response_model=List[NoticeResponse])
def get_my_uploaded_notices_cr(
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return get_cr_notices(db=db, cr=cr, skip=skip, limit=limit)


@router.get("/feed", response_model=List[NoticeResponse])
def get_teacher_notices_feed_for_cr(
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """CR feed: teacher notices for CR's dept/series and section (plus sectionless)."""
    return get_cr_feed_teacher_notices(db=db, cr=cr, skip=skip, limit=limit)


@router.get("/{notice_id}", response_model=NoticeResponse)
def get_my_notice_by_id_cr(
    notice_id: str,
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
):
    return get_cr_notice_by_id(db=db, cr=cr, notice_id=notice_id)


@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_my_notice_cr(
    notice_id: str,
    payload: CRNoticeUpdate,
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """
    Updates a CR notice.

    Handled inside service:
    - fields updated selectively
    - vector embeddings re-generated if content changed
    """
    notice = update_cr_notice(db=db, cr=cr, notice_id=notice_id, payload=payload)
    if background_tasks is not None:
        background_tasks.add_task(send_notice_push_by_id, str(notice.id))
    return notice


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_notice_cr(
    notice_id: str,
    cr: CR = Depends(get_current_cr),
    db: Session = Depends(get_db),
):
    delete_cr_notice(db=db, cr=cr, notice_id=notice_id)
    return None
