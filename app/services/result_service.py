from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.result_sheet_models import ResultSheet
from app.schemas.backend_schemas.result_schemas import ResultSheetCreate

from typing import Optional

def get_teacher_sheet_or_404(db: Session, sheet_id: str, teacher_id: str) -> ResultSheet:
    sheet = (
        db.query(ResultSheet)
        .filter(
            ResultSheet.id == sheet_id,
            ResultSheet.created_by_teacher_id == teacher_id,
        )
        .first()
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Result sheet not found")
    return sheet





def generate_result_sheet_title(payload: ResultSheetCreate) -> str:
    """
    Generates a human-friendly title for ResultSheet history.

    Format:
    <course_code> CT-<ct_no|-> | <dept>-<series>[-<section>] | <start>-<end>

    Examples:
    - "CSE-2100 CT-1 | CSE-23-C | 121-181"
    - "CSE-2100 CT-- | CSE-23 | -"
    """
    course = payload.course_code.strip().upper()

    ct_part = f"CT-{payload.ct_no}" if payload.ct_no is not None else "CT--"

    dept = payload.dept.strip().upper()
    series = payload.series
    section = payload.section.strip().upper() if payload.section else None

    group_part = f"{dept}-{series}" + (f"-{section}" if section else "")

    start = payload.starting_roll.strip() if payload.starting_roll else ""
    end = payload.ending_roll.strip() if payload.ending_roll else ""
    range_part = f"{start}-{end}" if (start or end) else "-"

    return f"{course} {ct_part} | {group_part} | {range_part}"
