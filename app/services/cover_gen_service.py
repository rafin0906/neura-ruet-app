import json
from typing import Dict, List
from sqlalchemy.orm import Session

from pathlib import Path
from datetime import datetime
import re


from app.ai.sys_prompts import (
    COVER_INFO_JSON_PROMPT,
    COVER_MISSING_FIELDS_PROMPT,
    COVER_TYPE_JSON_PROMPT,
)

# import your existing function (adjust path)
from app.services.cover_generator import generate_ruet_cover_pdf
import logging

logger = logging.getLogger(__name__)

COMMON_REQUIRED = [
    "cover_type_no",
    "course_code",
    "course_title",
    "date_of_submission",
    "session",
    "teacher_name",
    "teacher_designation",
    "teacher_dept",
    "full_name",
    "roll_no",
    "dept",
    "series",
]

REQUIRED_LAB = COMMON_REQUIRED + ["date_of_exp"]
REQUIRED_ASSIGNMENT = COMMON_REQUIRED
REQUIRED_REPORT = COMMON_REQUIRED


DEPT_MAPPING = {
    "EEE": "Department of Electrical & Electronic Engineering",
    "CSE": "Department of Computer Science & Engineering",
    "ETE": "Department of Electronics & Telecommunication Engineering",
    "ECE": "Department of Electrical & Computer Engineering",
    "CE": "Department of Civil Engineering",
    "URP": "Department of Urban & Regional Planning",
    "ARCH": "Department of Architecture",
    "BECM": "Department of Building Engineering & Construction Management",
    "ME": "Department of Mechanical Engineering",
    "IPE": "Department of Industrial & Production Engineering",
    "CME": "Department of Ceramic & Metallurgical Engineering",
    "MTE": "Department of Mechatronics Engineering",
    "MSE": "Department of Materials Science & Engineering",
    "CHE": "Department of Chemical Engineering",
}


def _safe_filename(text: str) -> str:
    text = text.strip().replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_\-]", "", text)
    return text


def get_student_profile_context(student) -> Dict[str, str]:
    dept_code = (getattr(student, "dept", "") or "").strip().upper()
    dept_full = DEPT_MAPPING.get(
        dept_code, dept_code
    )  # Use full name or keep original if not found

    series_raw = str(getattr(student, "series", "") or "").strip()
    series_formatted = f"Series {series_raw}" if series_raw else ""

    return {
        "full_name": getattr(student, "full_name", "")
        or getattr(student, "name", "")
        or "",
        "roll_no": str(
            getattr(student, "roll_no", "") or getattr(student, "roll", "") or ""
        ),
        "dept": dept_full,
        "section": getattr(student, "section", "") or getattr(student, "sec", "") or "",
        "series": series_formatted,
    }


def _safe_parse_json(raw: str) -> dict:
    if raw is None:
        raise ValueError("Cover JSON extractor returned empty output")

    text = str(raw).strip()
    if not text:
        raise ValueError("Cover JSON extractor returned empty output")

    # Common LLM formatting: fenced blocks like ```json { ... } ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text.strip())

    try:
        return json.loads(text)
    except Exception:
        # Fallback: extract the first JSON object from surrounding text.
        s = text.find("{")
        e = text.rfind("}")
        if s == -1 or e == -1 or e <= s:
            raise ValueError("Cover JSON extractor did not return JSON")
        return json.loads(text[s : e + 1])


def _merge(profile: Dict[str, str], extracted: Dict[str, str]) -> Dict[str, str]:
    payload = {
        # from LLM
        "cover_type_no": extracted.get("cover_type_no", "") or "",
        "cover_type_title": extracted.get("cover_type_title", "") or "",
        "course_code": extracted.get("course_code", "") or "",
        "course_title": extracted.get("course_title", "") or "",
        "date_of_exp": extracted.get("date_of_exp", "") or "",
        "date_of_submission": extracted.get("date_of_submission", "") or "",
        "session": extracted.get("session", "") or "",
        "teacher_name": extracted.get("teacher_name", "") or "",
        "teacher_designation": extracted.get("teacher_designation", "") or "",
        "teacher_dept": extracted.get("teacher_dept", "") or "",
        # server truth
        "full_name": profile.get("full_name", "") or "",
        "roll_no": profile.get("roll_no", "") or "",
        "dept": profile.get("dept", "") or "",
        "section": profile.get("section", "") or "",
        "series": profile.get("series", "") or "",
    }
    return payload


def _missing_fields(payload: Dict[str, str], cover_type: str) -> List[str]:
    if cover_type == "lab_report":
        required = REQUIRED_LAB
    elif cover_type == "assignment":
        required = REQUIRED_ASSIGNMENT
    elif cover_type == "report":
        required = REQUIRED_REPORT
    else:
        return []

    missing = []
    for key in required:
        if not str(payload.get(key, "")).strip():
            missing.append(key)

    return missing


async def run_cover_generator_pipeline(
    db: Session,
    room_id: str,
    student,
    user_text: str,
    history: List[Dict[str, str]],
    llm,
) -> str:
    profile_ctx = get_student_profile_context(student)

    raw_type = await llm.complete(
        system_prompt=COVER_TYPE_JSON_PROMPT,
        messages=history + [{"role": "user", "content": user_text}],
        # Keep json_mode disabled here because the WRONG-TOOL GUARD may return a plain sentence.
        json_mode=False,
        temperature=0.0,
        max_tokens=120,
    )
    try:
        type_data = _safe_parse_json(raw_type)
    except Exception as e:
        logger.error(f"Error parsing cover type JSON: {e}")
        return raw_type

    cover_type = (type_data.get("cover_type") or "").strip()

    if cover_type == "ask" or cover_type not in ("lab_report", "assignment", "report"):
        return (
            "Which cover do you want?\n"
            "• Lab report (Experiment)\n"
            "• Assignment\n"
            "• Report\n"
            "Reply with one of these."
        )

    # 1) extract JSON
    raw = await llm.complete(
        system_prompt=COVER_INFO_JSON_PROMPT,
        messages=[
            {"role": "system", "content": f"cover_type={cover_type}"},
            *history,
            {"role": "user", "content": user_text},
        ],
        json_mode=True,
        temperature=0.0,
        max_tokens=250,
    )

    try:
        logger.info((f"raw extracted for cover generation: {raw}"))
        extracted = _safe_parse_json(raw)
    except Exception as e:
        logger.error("Error parsing cover info JSON: %s", e)
        return raw
    # 2) merge + validate
    payload = _merge(profile_ctx, extracted)
    missing = _missing_fields(payload, cover_type)

    # 3) if missing -> ask user (RETURN STRING)
    if missing:
        logger.info(f"===================Missing CALLED===================")
        ask = await llm.complete(
            system_prompt=COVER_MISSING_FIELDS_PROMPT,
            messages=[
                {"role": "system", "content": f"Missing fields: {missing}"},
                *history,
                {"role": "user", "content": user_text},
            ],
            json_mode=False,
            temperature=0.4,
            max_tokens=180,
        )
        return ask

    # 4) convert exp_no
    try:
        cover_no = str(payload["cover_type_no"]).strip()
        cover_no_int = int(cover_no)
    except Exception:
        return "Cover number is invalid. Please provide a valid number (e.g. 1, 2, 3)."

    # --- base directories ---
    BASE_DIR = Path(__file__).resolve().parents[1]  # app/
    PDF_DIR = BASE_DIR / "assets" / "pdf"
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # --- dynamic filename ---
    course = _safe_filename(payload["course_code"])
    roll = _safe_filename(payload["roll_no"])
    cover_no = _safe_filename(payload["cover_type_no"])
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    type_token = {
        "lab_report": "Exp",
        "assignment": "Ass",
        "report": "Report",
    }[cover_type]

    filename = f"{course}_{type_token}-{cover_no}_Roll-{roll}_{ts}.pdf"

    output_path = PDF_DIR / filename

    # 5) call your generator
    cover_type_label = {
        "lab_report": "Experiment",
        "assignment": "Assignment",
        "report": "Report",
    }[cover_type]

    result = generate_ruet_cover_pdf(
        output_path=str(output_path),
        cover_type=cover_type_label,
        cover_type_no=str(payload["cover_type_no"]).zfill(2),
        cover_type_title=payload["cover_type_title"],
        course_code=payload["course_code"],
        course_title=payload["course_title"],
        date_of_exp=payload["date_of_exp"] if cover_type == "lab_report" else "",
        date_of_submission=payload["date_of_submission"],
        full_name=payload["full_name"],
        roll_no=payload["roll_no"],
        dept=payload["dept"],
        section=payload["section"],
        series=payload["series"],
        session=payload["session"],
        teacher_name=payload["teacher_name"],
        teacher_designation=payload["teacher_designation"],
        teacher_dept=payload["teacher_dept"],
        logo_path="../assets/images/ruet_logo.png",
        doodle_top_left_path=None,
        doodle_top_right_path=None,
        alice_ttf_path="../assets/fonts/Alice-Regular.ttf",
        futura_ttf_path="../assets/fonts/Futura.ttf",
        cormorant_ttf_path="../assets/fonts/CormorantGaramond-Light.ttf",
    )

    # In production, MUST ADD Hosting Server URL before the download path, e.g.:
    # download_url = f"https://yourdomain.com/downloads/{filename}" for letter use
    download_url = f"https://neura-ruet-app.onrender.com/downloads/{filename}"
    # download_url = f"/downloads/{filename}"

    return (
        "🎉 Cover page generated successfully.\n\n" f"📄 Download PDF:\n{download_url}"
    )
