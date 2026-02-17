# app/services/view_notice_service.py

import json
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging

from app.ai.llm_client import GroqClient
from app.ai.sys_prompts import NOTICE_LLM_SYSTEM_PROMPT
from app.ai.embedding_client import HFEmbeddingClient

from app.models.notice_models import Notice

logger = logging.getLogger(__name__)

def _profile_context(student) -> str:
    sec = getattr(student, "section", None) or getattr(student, "sec", None)
    dept = getattr(student, "dept", None)
    series = getattr(student, "series", None)
    if sec is None or (isinstance(sec, str) and sec.strip().lower() in {"", "none", "null"}):
        return f"Student profile: dept={dept}, series={series}"
    return f"Student profile: dept={dept}, sec={sec}, series={series}"


def _query_template(student, user_text: str) -> str:
    sec = getattr(student, "section", None) or getattr(student, "sec", None)
    dept = getattr(student, "dept", None)
    series = getattr(student, "series", None)
    if sec is None or (isinstance(sec, str) and sec.strip().lower() in {"", "none", "null"}):
        return f"A student from dept {dept}, series {series} is looking for notices. Query: {user_text}"
    return f"A student from dept {dept}, section {sec}, series {series} is looking for notices. Query: {user_text}"


def _normalize_section(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "" or cleaned.lower() in {"none", "null"}:
            return None
        upper = cleaned.upper()
        return upper if upper in {"A", "B", "C"} else None
    return None


def _serialize_row(row: Any) -> Dict[str, Any]:
    created_by_role = getattr(row, "created_by_role", None)

    teacher_obj = getattr(row, "teacher", None)
    cr_obj = getattr(row, "cr", None)

    teacher_name = getattr(teacher_obj, "full_name", None) if teacher_obj else None
    cr_name = getattr(cr_obj, "full_name", None) if cr_obj else None

    created_by_name = teacher_name if created_by_role == "teacher" else cr_name

    return {
        "id": getattr(row, "id", None),
        "title": getattr(row, "title", None),
        "notice_message": getattr(row, "notice_message", None),
        "created_by_role": created_by_role,

        # ✅ names instead of IDs
        "created_by_name": created_by_name,
        "teacher_name": teacher_name,
        "cr_name": cr_name,

        "dept": getattr(row, "dept", None),
        "sec": getattr(row, "sec", None),
        "series": getattr(row, "series", None),
        "created_at": str(getattr(row, "created_at", "")),
    }


def _similarity_search(
    db: Session,
    query_vec: List[float],
    student,
    top_k: int = 5,
):
    dept = getattr(student, "dept", None)
    sec = getattr(student, "section", None) or getattr(student, "sec", None)
    series = str(getattr(student, "series", "") or "")

    if not dept or not series:
        return []

    sec_norm = _normalize_section(sec)

    q = db.query(Notice).filter(Notice.vector_embeddings.isnot(None))

    # ✅ STRICT ACCESS CONTROL
    q = q.filter(Notice.dept == dept)
    q = q.filter(Notice.series == series)

    # If student has section, allow matching section + section-less notices.
    # If student has no section, only allow section-less notices.
    if sec_norm is None:
        q = q.filter(Notice.sec.is_(None))
    else:
        q = q.filter(or_(Notice.sec == sec_norm, Notice.sec.is_(None)))

    distance = Notice.vector_embeddings.l2_distance(query_vec)

    return q.order_by(distance.asc()).limit(top_k).all()


async def run_view_notices_pipeline(
    db: Session,
    room_id: str,
    student,
    user_text: str,
    history: List[Dict[str, str]],
    llm: GroqClient,
    top_k: int = 5,
) -> str:
    embedder = HFEmbeddingClient()

    profile_ctx = _profile_context(student)

    qtext = _query_template(student, user_text)
    qvec = await embedder.embed(qtext)

    rows = _similarity_search(db, qvec, student, top_k=top_k)

    # ===================DEBUG LOGGING===================
    serialized_rows = [_serialize_row(r) for r in rows]
    logger.info(
    "view_notices | retrieved rows content:\n%s",
    json.dumps(serialized_rows, indent=2))
    # ===================DEBUG LOGGING===================

    bundle = [_serialize_row(r) for r in rows]

    answer_messages = [
        {"role": "user", "content": profile_ctx},
        {"role": "user", "content": f"User query: {user_text}"},
        {"role": "user", "content": f"Top {top_k} retrieved notices (JSON): {json.dumps(bundle)}"},
    ]

    return await llm.complete(
        system_prompt=NOTICE_LLM_SYSTEM_PROMPT,
        messages=history + answer_messages,
        json_mode=False,
        temperature=0.3,
        max_tokens=700,
    )
