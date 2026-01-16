from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.notice_schemas import TeacherNoticeCreate, NoticeResponse, TeacherNoticeUpdate
from app.services.dependencies import get_current_teacher
from app.services.notice_service import (
    create_notice_by_teacher,
    get_teacher_notices,
    get_teacher_notice_by_id,
    update_teacher_notice,
    delete_teacher_notice,
)
from app.models.teacher_models import Teacher

router = APIRouter(prefix="/teacher/notices", tags=["Notices (Teacher)"])


@router.post("", response_model=NoticeResponse)
def upload_notice_teacher(
    payload: TeacherNoticeCreate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    return create_notice_by_teacher(db=db, payload=payload, teacher=teacher)


@router.get("", response_model=list[NoticeResponse])
def get_my_uploaded_notices_teacher(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return get_teacher_notices(db=db, teacher=teacher, skip=skip, limit=limit)


@router.get("/{notice_id}", response_model=NoticeResponse)
def get_my_notice_by_id_teacher(
    notice_id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    return get_teacher_notice_by_id(db=db, teacher=teacher, notice_id=notice_id)

@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_my_notice_teacher(
    notice_id: str,
    payload: TeacherNoticeUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    return update_teacher_notice(db=db, teacher=teacher, notice_id=notice_id, payload=payload)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_notice_teacher(
    notice_id: str,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    delete_teacher_notice(db=db, teacher=teacher, notice_id=notice_id)
    return None