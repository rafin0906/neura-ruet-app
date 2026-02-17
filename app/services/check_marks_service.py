# app/services/check_marks_service.py

import json
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.ai.sys_prompts import CHECK_MARKS_JSON_PROMPT, CHECK_MARKS_ANSWER_PROMPT
from app.schemas.ai_schemas.check_marks_schema import CheckMarksExtracted

from app.models.result_sheet_models import ResultSheet
from app.models.result_entry_models import ResultEntry
from app.models.teacher_models import Teacher  # adjust import path
from app.ai.llm_client import GroqClient

import logging
logger = logging.getLogger(__name__)

def _normalize_course_code(raw: str) -> str:
    """
    Server-side safety normalization (don’t trust only LLM).
    Accept: cse1202 / cse 1202 / cse-1202 -> CSE-1202
    """
    if not raw:
        return ""
    s = raw.strip().upper().replace(" ", "").replace("_", "-")
    # if "CSE1202" -> insert hyphen after 3 letters
    if len(s) == 7 and s[:3].isalpha() and s[3:].isdigit():
        return f"{s[:3]}-{s[3:]}"
    # if "CSE-1202" ok
    if len(s) == 8 and s[:3].isalpha() and s[3] == "-" and s[4:].isdigit():
        return s
    # try to recover patterns like "CSE--1202" etc
    s = s.replace("--", "-")
    if len(s) >= 8 and s[:3].isalpha() and "-" in s:
        parts = s.split("-")
        if len(parts) >= 2 and parts[0].isalpha() and parts[1].isdigit():
            left = parts[0][:3]
            right = parts[1][:4]
            if len(left) == 3 and len(right) == 4:
                return f"{left}-{right}"
    return ""


def _course_code_key(code: str) -> str:
    return "".join(ch for ch in str(code).upper() if ch.isalnum())


def _normalize_roll(roll_full: str) -> str:
    # Keep the full numeric roll. Example: "2303137" -> "2303137"
    if not roll_full:
        return ""
    return "".join(ch for ch in str(roll_full) if ch.isdigit())


async def _extract_json(llm: GroqClient, user_text: str, history: List[Dict[str, str]]) -> CheckMarksExtracted:
    raw = await llm.complete(
        system_prompt=CHECK_MARKS_JSON_PROMPT,
        messages=history + [{"role": "user", "content": user_text}],
        json_mode=True,
        temperature=0.1,
        max_tokens=160,
    )

    
    try:
        data = json.loads(raw)
        logger.info(f"LLM raw output: {raw}")
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        data = (
            json.loads(raw[start:end + 1])
            if start != -1 and end != -1
            else {
                "mode": "ask",
                "question": "Please provide course code and CT number (e.g., CSE-1202 CT-2).",
                "missing_fields": ["course_code", "ct_no"],
            }
        )

    parsed = CheckMarksExtracted.model_validate(data)


    if parsed.mode == "ok":
        parsed.course_code = _normalize_course_code(parsed.course_code)

        # server safety: if still missing, force ask
        missing = []
        if not parsed.course_code:
            missing.append("course_code")
        if parsed.ct_no is None:
            missing.append("ct_no")
        if missing:
            return CheckMarksExtracted(
                mode="ask",
                question="Please provide course code and CT number (e.g., CSE-1202 CT-2).",
                missing_fields=missing,
            )

    logger.info(f"Parsed CheckMarksExtracted: {parsed}")

    return parsed



async def run_check_marks_pipeline(
    db: Session,
    room_id: str,
    student,
    user_text: str,
    history: List[Dict[str, str]],
    llm: GroqClient,
) -> str:
    """
    Tool handler signature matches your run_tool_chat usage.
    """

    # 1) LLM JSON
    extracted = await _extract_json(llm, user_text, history)

    if extracted.mode == "wrong_tool":
        return extracted.message or "This is not a marks request. Please use the correct tool."

    if extracted.mode == "ask":
        return extracted.question or "Please provide course code and CT number."


    # 2) Merge profile ctx
    # Adjust these attribute names to your student model fields
    std_dept = getattr(student, "dept", None)
    std_section = getattr(student, "section", None) or getattr(student, "sec", None)
    std_series = str(getattr(student, "series", "") or "")
    std_roll_full = getattr(student, "roll_no", None) or getattr(student, "roll", None) or ""

    roll_full_digits = _normalize_roll(str(std_roll_full))
    if not roll_full_digits:
        return "Your roll number is not set in your profile. Please update your profile roll number."


    # 3) Query result_sheets with student scope
    # If student's section is missing, do NOT block; try to find the sheet that contains their roll entry.
    sheet = None
    entry = None
    course_key = _course_code_key(extracted.course_code)
    if std_section:
        sheet = (
            db.query(ResultSheet)
            .filter(ResultSheet.dept == std_dept)
            .filter(ResultSheet.section == std_section)
            .filter(ResultSheet.series == std_series)
            .filter(func.regexp_replace(func.upper(ResultSheet.course_code), r"[^A-Z0-9]", "", "g") == course_key)
            .filter(ResultSheet.ct_no == extracted.ct_no)
            .order_by(desc(ResultSheet.created_at))
            .first()
        )
        if sheet:
            entry = (
                db.query(ResultEntry)
                .filter(ResultEntry.result_sheet_id == sheet.id)
                .filter(ResultEntry.roll_no == roll_full_digits)
                .first()
            )
    else:
        candidate_sheets = (
            db.query(ResultSheet)
            .filter(ResultSheet.dept == std_dept)
            .filter(ResultSheet.series == std_series)
            .filter(func.regexp_replace(func.upper(ResultSheet.course_code), r"[^A-Z0-9]", "", "g") == course_key)
            .filter(ResultSheet.ct_no == extracted.ct_no)
            .order_by(desc(ResultSheet.created_at))
            .all()
        )
        for s in candidate_sheets:
            e = (
                db.query(ResultEntry)
                .filter(ResultEntry.result_sheet_id == s.id)
                .filter(ResultEntry.roll_no == roll_full_digits)
                .first()
            )
            if e:
                sheet = s
                entry = e
                break

    if not sheet:
        return f"No result sheet found for {extracted.course_code} CT-{extracted.ct_no} in your series."
    
    course_name = sheet.course_name or "Unknown"

    if not entry:
        return f"Your marks for {extracted.course_code} CT-{extracted.ct_no} are not available yet (or not published for your roll)."

    marks = entry.marks

    # 5) Teacher lookup
    teacher_name = "Unknown"
    if sheet.created_by_teacher_id:
        t = db.query(Teacher).filter(Teacher.id == sheet.created_by_teacher_id).first()
        if t:
            teacher_name = getattr(t, "full_name", None) or getattr(t, "name", None) or "Unknown"

    # 6) Answer LLM (grounded)
    grounded_ctx = {
        "course_code": extracted.course_code,
        "course_name": course_name,
        "ct_no": extracted.ct_no,
        "marks": marks,
        "teacher_name": teacher_name,
    }

    # Debug log: record which roll and marks were fetched from DB
    try:
        logger.info(
            "check_marks: fetched -> roll=%s sheet_id=%s ct=%s marks=%s",
            roll_full_digits,
            getattr(sheet, 'id', None),
            extracted.ct_no,
            marks,
        )
    except Exception:
        logger.exception("check_marks: failed to log fetched marks info")

    # Also log the exact DB context we will provide to the LLM
    try:
        logger.info("check_marks: LLM DB_CONTEXT: %s", json.dumps(grounded_ctx))
    except Exception:
        logger.exception("check_marks: failed to log DB_CONTEXT")

    # SECURITY: Do NOT include user messages or conversation history when generating
    # the grounded answer. The model must respond strictly from DB_CONTEXT and must
    # not be influenced by any user claims (e.g., "I got 25").
    answer = await llm.complete(
        system_prompt=CHECK_MARKS_ANSWER_PROMPT,
        messages=[{"role": "assistant", "content": f"DB_CONTEXT: {json.dumps(grounded_ctx)}"}],
        json_mode=False,
        temperature=0.0,
        max_tokens=120,
    )

    # Trim whitespace to avoid extra leading/trailing spaces in the UI message
    try:
        if isinstance(answer, str):
            answer = answer.strip()
    except Exception:
        logger.exception("check_marks: failed to trim answer")

    return answer
