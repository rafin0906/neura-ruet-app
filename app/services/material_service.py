from __future__ import annotations
from fastapi import HTTPException, status

import re
from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import asc, desc, case, literal, or_, cast, String
from sqlalchemy.sql.elements import ColumnElement

from app.models.class_note_models import ClassNote
from app.models.ct_question_models import CTQuestion
from app.models.lecture_slide_models import LectureSlide
from app.models.semester_question_models import SemesterQuestion
from app.schemas.ai_schemas.find_materials_schemas import (
    FindMaterialsLLMOutput,
    MaterialType,
    MatchMode,
    SortBy,
)



def get_class_note_or_404(db: Session, note_id: str) -> ClassNote:
    note = db.query(ClassNote).filter(ClassNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Class note not found")
    return note


def ensure_cr_owns_note(note: ClassNote, cr_id: str):
    if note.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_ct_question_or_404(db: Session, ct_id: str) -> CTQuestion:
    obj = db.query(CTQuestion).filter(CTQuestion.id == ct_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="CT Question not found")
    return obj


def ensure_cr_owns_ct_question(obj: CTQuestion, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_lecture_slide_or_404(db: Session, slide_id: str) -> LectureSlide:
    obj = db.query(LectureSlide).filter(LectureSlide.id == slide_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Lecture slide not found")
    return obj


def ensure_cr_owns_lecture_slide(obj: LectureSlide, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def get_semester_question_or_404(db: Session, sq_id: str) -> SemesterQuestion:
    obj = db.query(SemesterQuestion).filter(SemesterQuestion.id == sq_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Semester question not found")
    return obj


def ensure_cr_owns_semester_question(obj: SemesterQuestion, cr_id: str):
    if obj.uploaded_by_cr_id != str(cr_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")





# -----------------------------
# Normalization helpers
# -----------------------------

_course_code_re = re.compile(r"^([A-Za-z]{2,6})[-\s_]?(\d{3,5})$")


def _norm_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    return s if s else None


def _norm_course_code(s: Optional[str]) -> Optional[str]:
    """
    Normalizes:
      "cse 2100" / "CSE2100" / "CSE-2100" -> "CSE-2100"
    If it doesn't match the pattern, returns cleaned uppercase.
    """
    s = _norm_text(s)
    if not s:
        return None
    s2 = s.replace(" ", "").replace("_", "-").upper()
    m = _course_code_re.match(s2.replace("-", ""))
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return s2.upper()


def _like_pattern(s: str) -> str:
    return f"%{s.strip()}%"


def _series_from_profile(parsed_series: Optional[Any], profile_series: Optional[Any], Model) -> Optional[Any]:
    """
    Avoids the common bug: DB series is INT but you cast to str.
    If Model.series is a String column, use str; otherwise keep int-ish.
    """
    if parsed_series is not None:
        return parsed_series

    if profile_series is None:
        return None

    try:
        # crude but effective: if column is String-ish, store as string
        if isinstance(getattr(Model, "series").type, String):
            return str(profile_series)
    except Exception:
        pass

    return profile_series


# -----------------------------
# Scoring / ranking helpers
# -----------------------------

def _score_expr(
    *,
    Model,
    course_code: Optional[str],
    course_name: Optional[str],
    topic: Optional[str],
    written_by: Optional[str],
    ct_no: Optional[int],
    year: Optional[int],
) -> ColumnElement:
    """
    Builds a SQL expression that scores each row.
    Higher score = better match.
    """
    score = literal(0)

    # course_code is the strongest signal
    if course_code and hasattr(Model, "course_code"):
        score = score + case(
            (Model.course_code == course_code, 100),
            (Model.course_code.ilike(_like_pattern(course_code)), 60),
            else_=0,
        )

    # course_name
    if course_name and hasattr(Model, "course_name"):
        score = score + case(
            (Model.course_name.ilike(_like_pattern(course_name)), 50),
            else_=0,
        )

    # topic
    if topic and hasattr(Model, "topic"):
        score = score + case(
            (Model.topic.ilike(_like_pattern(topic)), 40),
            else_=0,
        )

    # written_by
    if written_by and hasattr(Model, "written_by"):
        score = score + case(
            (Model.written_by.ilike(_like_pattern(written_by)), 20),
            else_=0,
        )

    # ct_no / year are strict signals
    if ct_no is not None and hasattr(Model, "ct_no"):
        score = score + case((Model.ct_no == ct_no, 20), else_=0)

    if year is not None and hasattr(Model, "year"):
        score = score + case((Model.year == year, 20), else_=0)

    return score


def _apply_scope_filters(q, Model, dept: Optional[str], sec: Optional[str], series: Optional[Any]):
    """
    Hard filters (scope): dept, sec, series.
    These should not be fuzzy.
    """
    if dept and hasattr(Model, "dept"):
        q = q.filter(Model.dept == dept)
    if sec and hasattr(Model, "sec"):
        q = q.filter(Model.sec == sec)
    if series is not None and hasattr(Model, "series"):
        q = q.filter(Model.series == series)
    return q


def _apply_phase_filters(
    q,
    Model,
    *,
    phase: str,
    course_code: Optional[str],
    course_name: Optional[str],
    topic: Optional[str],
    written_by: Optional[str],
    ct_no: Optional[int],
    year: Optional[int],
):
    """
    Two-phase search:
      phase="strict": exact where possible
      phase="broad": partial matching + OR-style text matching
    """
    # Strict phase: only apply provided fields as strong constraints
    if phase == "strict":
        if course_code and hasattr(Model, "course_code"):
            q = q.filter(Model.course_code == course_code)

        if ct_no is not None and hasattr(Model, "ct_no"):
            q = q.filter(Model.ct_no == ct_no)

        if year is not None and hasattr(Model, "year"):
            q = q.filter(Model.year == year)

        # For text fields, strict = "contains" is OK, but still ANDed
        if course_name and hasattr(Model, "course_name"):
            q = q.filter(Model.course_name.ilike(_like_pattern(course_name)))

        if topic and hasattr(Model, "topic"):
            q = q.filter(Model.topic.ilike(_like_pattern(topic)))

        if written_by and hasattr(Model, "written_by"):
            q = q.filter(Model.written_by.ilike(_like_pattern(written_by)))

        return q

    # Broad phase: loosen matching and allow OR across text signals
    text_ors = []

    if course_code and hasattr(Model, "course_code"):
        text_ors.append(Model.course_code.ilike(_like_pattern(course_code)))

    if course_name and hasattr(Model, "course_name"):
        text_ors.append(Model.course_name.ilike(_like_pattern(course_name)))

    if topic and hasattr(Model, "topic"):
        text_ors.append(Model.topic.ilike(_like_pattern(topic)))

    if written_by and hasattr(Model, "written_by"):
        text_ors.append(Model.written_by.ilike(_like_pattern(written_by)))

    # Still keep ct_no/year if present (they're strong)
    if ct_no is not None and hasattr(Model, "ct_no"):
        q = q.filter(Model.ct_no == ct_no)

    if year is not None and hasattr(Model, "year"):
        q = q.filter(Model.year == year)

    if text_ors:
        q = q.filter(or_(*text_ors))

    return q


def find_materials_handler(*, db: Session, parsed: FindMaterialsLLMOutput, student_profile: dict):
    # 0) Fill missing context (scope)
    dept = _norm_text(parsed.dept) or _norm_text(student_profile.get("dept"))
    sec = _norm_text(parsed.sec) or _norm_text(student_profile.get("section"))

    # 1) Pick model/table
    if parsed.material_type == MaterialType.class_note:
        Model = ClassNote
    elif parsed.material_type == MaterialType.ct_question:
        Model = CTQuestion
    elif parsed.material_type == MaterialType.lecture_slide:
        Model = LectureSlide
    else:
        Model = SemesterQuestion

    # 2) Normalize query signals
    course_code = _norm_course_code(parsed.course_code)
    course_name = _norm_text(getattr(parsed, "course_name", None))
    topic = _norm_text(getattr(parsed, "topic", None))
    written_by = _norm_text(getattr(parsed, "written_by", None))
    ct_no = getattr(parsed, "ct_no", None)
    year = getattr(parsed, "year", None)

    series = _series_from_profile(getattr(parsed, "series", None), student_profile.get("series"), Model)

    # 3) Base query with hard scope filters
    base = db.query(Model)
    base = _apply_scope_filters(base, Model, dept, sec, series)

    # 4) Two-phase search:
    #    A) strict, B) broad (if strict returns nothing)
    def run_phase(phase: str):
        q = base
        q = _apply_phase_filters(
            q,
            Model,
            phase=phase,
            course_code=course_code,
            course_name=course_name,
            topic=topic,
            written_by=written_by,
            ct_no=ct_no,
            year=year,
        )

        score = _score_expr(
            Model=Model,
            course_code=course_code,
            course_name=course_name,
            topic=topic,
            written_by=written_by,
            ct_no=ct_no,
            year=year,
        ).label("match_score")

        # Order by score first, then created_at direction
        if parsed.sort_by == SortBy.newest:
            q = q.add_columns(score).order_by(desc(score), desc(Model.created_at))
        else:
            q = q.add_columns(score).order_by(desc(score), asc(Model.created_at))

        # paginate
        q = q.offset(parsed.offset).limit(parsed.limit)
        return q.all()

    rows_scored = run_phase("strict")
    if not rows_scored:
        rows_scored = run_phase("broad")

    # rows_scored is list of (ModelRow, score)
    items = []
    for tup in rows_scored:
        r = tup[0]  # model row
        score_val = tup[1] if len(tup) > 1 else None

        items.append(
            {
                "id": r.id,
                "drive_url": getattr(r, "drive_url", None),
                "course_code": getattr(r, "course_code", None),
                "course_name": getattr(r, "course_name", None),
                "topic": getattr(r, "topic", None),
                "ct_no": getattr(r, "ct_no", None),
                "year": getattr(r, "year", None),
                "written_by": getattr(r, "written_by", None),
                "dept": getattr(r, "dept", None),
                "sec": getattr(r, "sec", None),
                "series": getattr(r, "series", None),
                "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
                "match_score": int(score_val) if score_val is not None else None,
            }
        )

    return {
        "tool": "find_materials",
        "material_type": parsed.material_type.value,
        "query": parsed.model_dump(),
        "count": len(items),
        "items": items,  # respect parsed.limit; don't force [:5]
        "search_mode_used": "strict_then_broad",
    }
