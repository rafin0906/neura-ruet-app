# app/services/generate_marksheet_service.py
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.ai.sys_prompts import MARKSHEET_JSON_PROMPT
from app.models.result_sheet_models import ResultSheet
from app.services.mark_sheet_generator import generate_mark_sheet


def _normalize_course_code(code: str) -> str:
    # "cse 2101" / "cse2101" / "CSE-2101" -> "CSE-2101"
    c = code.strip().upper().replace(" ", "").replace("_", "-")
    if "-" not in c and len(c) >= 7:
        # naive split: ABC1234 -> ABC-1234
        c = f"{c[:3]}-{c[3:]}"
    return c


def _dept_full_name(dept_code: str) -> str:
    mapping = {
        "CSE": "Computer Science & Engineering",
        "EEE": "Electrical & Electronic Engineering",
        "CE": "Civil Engineering",
        "ETE": "Electronics & Telecommunication Engineering",
        "ECE": "Electrical & Computer Engineering",
        "ARCH": "Architecture",
        "URP": "Urban & Regional Planning",
        "ME": "Mechanical Engineering",
        "IPE": "Industrial & Production Engineering",
        "MTE": "Mechatronics Engineering",
        "GCE": "Glass & Ceramic Engineering",
        "CFPE": "Chemical & Food Process Engineering",
        "MSE": "Materials Science & Engineering",
    }
    return mapping.get(dept_code.upper().strip(), dept_code)


def _safe_filename(s: str) -> str:
    """Clean string for filename usage."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(s))


async def run_generate_marksheet_pipeline(
    db: Session,
    room_id: str,
    teacher,
    user_text: str,
    history: List[Dict[str, str]],
    llm,
) -> str:
    # 1) extract JSON
    raw = await llm.complete(
        system_prompt=MARKSHEET_JSON_PROMPT,
        messages=history + [{"role": "user", "content": user_text}],
        json_mode=True,
        temperature=0.1,
        max_tokens=250,
    )

    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse marksheet request JSON.")

    if data.get("mode") == "ask":
        return data.get("question", "Please provide missing info.")

    # 2) validate fields
    required = ["dept", "section", "series", "course_code", "ct_no"]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return f"Missing: {', '.join(missing)}"

    dept = str(data["dept"]).upper().strip()
    section = str(data["section"]).upper().strip()
    series = str(data["series"]).strip()
    course_code = _normalize_course_code(str(data["course_code"]))
    ct_list = data["ct_no"]

    if not isinstance(ct_list, list) or not all(isinstance(x, int) for x in ct_list):
        return "ct_no must be a list of integers like [1] or [1,2]."

    teacher_id = str(teacher.id)

    # 3) fetch all matching sheets for those CTs
    sheets: List[ResultSheet] = (
        db.query(ResultSheet)
        .options(selectinload(ResultSheet.entries))
        .filter(
            ResultSheet.created_by_teacher_id == teacher_id,
            ResultSheet.dept == dept,
            ResultSheet.section == section,
            ResultSheet.series == series,
            ResultSheet.course_code == course_code,
            ResultSheet.ct_no.in_(ct_list),
        )
        .all()
    )

    if not sheets:
        return "No matching result sheets found for your request."

    found_cts = {s.ct_no for s in sheets}
    missing_cts = [c for c in ct_list if c not in found_cts]
    if missing_cts:
        return f"Sheets missing for CT: {missing_cts}. Create them first, then upload entries."

    # 4) build marks_batch_entries = [{roll_no, ct_no, marks}, ...]
    marks_batch_entries: List[Dict[str, Any]] = []
    for s in sheets:
        for e in s.entries:
            marks_batch_entries.append(
                {"roll_no": str(e.roll_no), "ct_no": int(s.ct_no), "marks": str(e.marks)}
            )

    # 5) pick course_name from any sheet
    course_name = sheets[0].course_name

    # 6) determine from_roll/to_roll from sheet (fallback: min/max in entries)
    def _safe_int(x):
        try:
            return int(str(x))
        except Exception:
            return None

    all_rolls = [_safe_int(e["roll_no"]) for e in marks_batch_entries]
    all_rolls = [r for r in all_rolls if r is not None]

    from_roll = _safe_int(sheets[0].starting_roll) or (min(all_rolls) if all_rolls else 0)
    to_roll = _safe_int(sheets[0].ending_roll) or (max(all_rolls) if all_rolls else 0)

    # --- base directories ---
    BASE_DIR = Path(__file__).resolve().parents[1]  # app/
    PDF_DIR = BASE_DIR / "assets" / "pdf"
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # --- dynamic filename ---
    course = _safe_filename(course_code)
    dept_safe = _safe_filename(dept)
    section_safe = _safe_filename(section)
    series_safe = _safe_filename(series)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    ct_range = "_".join(map(str, sorted(ct_list)))

    filename = f"{course}_CT-{ct_range}_{dept_safe}-{series_safe}-{section_safe}_{ts}.pdf"
    output_path = PDF_DIR / filename

    # 7) generate pdf
    generate_mark_sheet(
        output_pdf_path=str(output_path),
        dept=_dept_full_name(dept),
        series=series,
        section=section,
        course_code=course_code,
        course_name=course_name,
        from_roll=from_roll,
        to_roll=to_roll,
        marks_batch_entries=marks_batch_entries,
    )

    # 8) return download URL with formatted success message
    # In production, MUST ADD Hosting Server URL before the download path, e.g.:
    # download_url = f"https://yourdomain.com/downloads/{filename}"
    download_url = f"/downloads/{filename}"

    return (
        "🎉 CT Marksheet generated successfully.\n\n"
        f"📄 Download PDF:\n{download_url}"
    )