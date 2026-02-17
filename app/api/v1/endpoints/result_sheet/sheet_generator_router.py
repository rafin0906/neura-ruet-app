from uuid import UUID
from typing import List
from sqlalchemy import desc

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.database import get_db
from app.services.dependencies import get_current_teacher

from app.models.result_sheet_models import ResultSheet
from app.models.result_entry_models import ResultEntry

from app.schemas.backend_schemas.result_schemas import (
    ResultSheetCreate,
    ResultSheetUpdate,
    ResultSheetResponse,
    ResultSheetBatchUpload,
    ResultSheetWithEntriesResponse,
    ResultSheetHistoryItem,
)

from app.services.result_service import get_teacher_sheet_or_404, generate_result_sheet_title


router = APIRouter(prefix="/result-sheets", tags=["Result Sheets (Teacher)"])



@router.post("/", response_model=ResultSheetResponse, status_code=status.HTTP_201_CREATED)
def create_result_sheet(
    payload: ResultSheetCreate,
    db: Session = Depends(get_db),
    teacher=Depends(get_current_teacher),
):

    exists = (
        db.query(ResultSheet.id)
        .filter(
            ResultSheet.created_by_teacher_id == str(teacher.id),
            ResultSheet.dept == payload.dept,
            ResultSheet.section == payload.section,
            ResultSheet.series == str(payload.series),
            ResultSheet.course_code == payload.course_code,
            ResultSheet.ct_no == payload.ct_no,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail="Result sheet already exists for this course and CT no."
        )

    
    sheet = ResultSheet(
        created_by_teacher_id=str(teacher.id),
        title=generate_result_sheet_title(payload),   #  generated on server
        ct_no=payload.ct_no,
        course_code=payload.course_code,
        course_name=payload.course_name,
        dept=payload.dept,
        section=payload.section,
        series=str(payload.series),
        starting_roll=payload.starting_roll,
        ending_roll=payload.ending_roll,
    )

    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet


@router.post("/{sheet_id}/entries/batch", status_code=status.HTTP_200_OK)
def batch_upsert_entries(
    sheet_id: UUID,
    payload: ResultSheetBatchUpload,
    db: Session = Depends(get_db),
    teacher=Depends(get_current_teacher),
):
    sheet_id_str = str(sheet_id)

    # ownership check
    get_teacher_sheet_or_404(db, sheet_id_str, str(teacher.id))

    rows = [
        {
            "result_sheet_id": sheet_id_str,
            "roll_no": e.roll_no,
            "marks": e.marks.strip().upper(),   # "A" or numeric
        }
        for e in payload.entries
    ]

    stmt = pg_insert(ResultEntry).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_result_entries_sheet_roll",
        set_={"marks": stmt.excluded.marks},
    )

    try:
        db.execute(stmt)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Results saved", "count": len(rows)}


@router.get("/get-by-id/{sheet_id}", response_model=ResultSheetWithEntriesResponse)
def get_sheet(
    sheet_id: UUID,
    db: Session = Depends(get_db),
    teacher=Depends(get_current_teacher),
):
    sheet_id_str = str(sheet_id)

    sheet = (
        db.query(ResultSheet)
        .options(selectinload(ResultSheet.entries))
        .filter(
            ResultSheet.id == sheet_id_str,
            ResultSheet.created_by_teacher_id == str(teacher.id),
        )
        .first()
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Result sheet not found")

    return sheet




@router.get("/get-all", response_model=List[ResultSheetHistoryItem])
def list_result_sheets_history(
    db: Session = Depends(get_db),
    teacher=Depends(get_current_teacher),
):
    sheets = (
        db.query(ResultSheet)
        .filter(ResultSheet.created_by_teacher_id == str(teacher.id))
        .order_by(desc(ResultSheet.created_at))
        .all()
    )
    return sheets


@router.patch("/{sheet_id}", response_model=ResultSheetResponse)
def update_result_sheet(
    sheet_id: UUID,
    payload: ResultSheetUpdate,
    db: Session = Depends(get_db),
    teacher=Depends(get_current_teacher),
):
    sheet_id_str = str(sheet_id)

    sheet = get_teacher_sheet_or_404(db, sheet_id_str, str(teacher.id))
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return sheet

    next_ct_no = updates.get("ct_no", sheet.ct_no)
    next_course_code = updates.get("course_code", sheet.course_code)
    next_course_name = updates.get("course_name", sheet.course_name)
    next_dept = updates.get("dept", sheet.dept)
    next_section = updates.get("section", sheet.section)
    next_series = updates.get("series", int(sheet.series) if sheet.series is not None else None)

    next_starting_roll = updates.get("starting_roll", sheet.starting_roll)
    next_ending_roll = updates.get("ending_roll", sheet.ending_roll)

    # uniqueness conflict check (same as create, but exclude self)
    exists = (
        db.query(ResultSheet.id)
        .filter(
            ResultSheet.id != sheet_id_str,
            ResultSheet.created_by_teacher_id == str(teacher.id),
            ResultSheet.dept == next_dept,
            ResultSheet.section == next_section,
            ResultSheet.series == str(next_series),
            ResultSheet.course_code == next_course_code,
            ResultSheet.ct_no == next_ct_no,
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail="Result sheet already exists for this course and CT no.",
        )

    # apply updates
    sheet.ct_no = next_ct_no
    sheet.course_code = next_course_code
    sheet.course_name = next_course_name
    sheet.dept = next_dept
    sheet.section = next_section
    sheet.series = str(next_series)
    sheet.starting_roll = next_starting_roll
    sheet.ending_roll = next_ending_roll

    # regenerate title to keep history correct
    sheet.title = generate_result_sheet_title(
        ResultSheetCreate(
            ct_no=next_ct_no,
            course_code=next_course_code,
            course_name=next_course_name,
            dept=next_dept,
            section=next_section,
            series=next_series,
            starting_roll=next_starting_roll,
            ending_roll=next_ending_roll,
        )
    )

    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return sheet
