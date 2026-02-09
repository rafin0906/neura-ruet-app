# app/services/find_materials_service.py

import json
from typing import Any, Dict, List, Tuple, Type
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.ai.llm_client import GroqClient
from app.ai.sys_prompts import MATERIAL_TYPE_JSON_PROMPT, ANSWER_SYSTEM_PROMPT
from app.ai.embedding_client import HFEmbeddingClient  # async HF client

from app.models.message_models import Message
from app.models.class_note_models import ClassNote
from app.models.lecture_slide_models import LectureSlide
from app.models.ct_question_models import CTQuestion
from app.models.semester_question_models import SemesterQuestion


ALLOWED_TYPES = {"classnote", "lectureslide", "ct_question", "semester_question"}

TYPE_TO_MODEL: Dict[str, Type] = {
    "classnote": ClassNote,
    "lectureslide": LectureSlide,
    "ct_question": CTQuestion,
    "semester_question": SemesterQuestion,
}


def _profile_context(user) -> str:
    sec = getattr(user, "section", None) or getattr(user, "sec", None)
    user_type = "Teacher" if hasattr(user, "teacher_id") or getattr(user, "role", None) == "teacher" else "Student"
    return (
        f"{user_type} profile: dept={getattr(user,'dept',None)}, "
        f"section={sec}, series={getattr(user,'series',None)}, "
        f"roll={getattr(user,'roll_no',None)}"
    )


def _query_template(user, user_text: str) -> str:
    user_type = "teacher" if hasattr(user, "teacher_id") or getattr(user, "role", None) == "teacher" else "student"
    return (
        f"A {user_type} from {user.dept} department asking: {user_text}. "
        f"Profile info: series={getattr(user,'series',None)}, section={getattr(user,'section',None)}"
    )


def _serialize_row(row: Any) -> Dict[str, Any]:
    return {
        "id": getattr(row, "id", None),
        "dept": getattr(row, "dept", None),
        "sec": getattr(row, "sec", None),
        "series": getattr(row, "series", None),

        "course_code": getattr(row, "course_code", None),
        "course_name": getattr(row, "course_name", None),

        # type-specific fields
        "written_by": getattr(row, "written_by", None),  # class note
        "topic": getattr(row, "topic", None),            # slides
        "ct_no": getattr(row, "ct_no", None),            # CT
        "year": getattr(row, "year", None),              # semester

        "drive_url": getattr(row, "drive_url", None),
        "created_at": str(getattr(row, "created_at", "")),
    }


async def _detect_material_type(
    llm: GroqClient,
    user_text: str,
    history: List[Dict[str, str]],
) -> Tuple[str, float]:
    raw = await llm.complete(
        system_prompt=MATERIAL_TYPE_JSON_PROMPT,
        messages=history + [{"role": "user", "content": user_text}],
        json_mode=True,
        temperature=0.1,
    )
    try:
        data = json.loads(raw)
        mtype = data.get("material_type")
        conf = float(data.get("confidence", 0.0))
        if mtype not in ALLOWED_TYPES:
            return "classnote", 0.0
        conf = max(0.0, min(conf, 1.0))
        return mtype, conf
    except Exception:
        return "classnote", 0.0


def _similarity_search(
    db: Session,
    model: Type,
    query_vec: List[float],
    user,
    top_k: int = 5,
):
    """
    Dept-only filter (forced from user profile).
    No filtering by series/section.
    """
    dept = getattr(user, "dept", None)
    if not dept:
        return []

    q = db.query(model).filter(model.vector_embeddings.isnot(None))

    # ✅ dept-only filter
    if hasattr(model, "dept"):
        q = q.filter(model.dept == dept)

    distance = model.vector_embeddings.l2_distance(query_vec)
    return q.order_by(distance.asc()).limit(top_k).all()


async def run_find_materials_pipeline(
    db: Session,
    room_id: str,
    student=None,
    teacher=None,
    user_text: str = "",
    history: List[Dict[str, str]] = None,
    llm: GroqClient = None,
    top_k: int = 5,
) -> str:
    """
    Tool handler. Orchestration (memory + gate) lives in ai_chat_service.py.
    This function assumes user_text is tool-related and should do retrieval.
    """
    # pick whichever context is provided
    user = teacher if teacher else student
    if not user:
        return "Error: No user context provided."

    if history is None:
        history = []

    embedder = HFEmbeddingClient()

    profile_ctx = _profile_context(user)

    # 1) detect material type
    material_type, confidence = await _detect_material_type(llm, user_text, history)
    model = TYPE_TO_MODEL[material_type]

    # 2) embed query
    qtext = _query_template(user, user_text)
    qvec = await embedder.embed(qtext)

    # 3) retrieve
    rows = _similarity_search(db, model, qvec, user, top_k=top_k)
    bundle = [_serialize_row(r) for r in rows]

    # 4) answer
    answer_messages = [
        {"role": "user", "content": profile_ctx},
        {"role": "user", "content": f"User question: {user_text}"},
        {"role": "user", "content": f"Detected material_type: {material_type} (confidence={confidence})"},
        {"role": "user", "content": f"Retrieved materials (JSON): {json.dumps(bundle)}"},
    ]

    final = await llm.complete(
        system_prompt=ANSWER_SYSTEM_PROMPT,
        messages=history + answer_messages,
        json_mode=False,
        temperature=0.4,
        max_tokens=900,
    )
    return final