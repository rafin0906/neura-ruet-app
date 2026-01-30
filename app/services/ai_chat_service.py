import json
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import ValidationError

from app.ai.tool_registry import get_tool, TOOL_REGISTRY
from app.ai.llm_client import LLMClient
from app.models.message_models import Message
from app.ai.intent_router import route_intent  # ✅ the new LLM gate (keep your old naming)


def _normalize_group_fields(parsed, profile: dict):
    """
    Enforce server-truth fields.
    - dept and series ALWAYS come from student profile dict
    """
    return parsed.model_copy(
        update={
            "dept": profile.get("dept"),
            "series": str(profile.get("series")) if profile.get("series") is not None else None,
        }
    )


def _fetch_last_messages(db: Session, room_id: str, limit: int = 6):
    msgs = (
        db.query(Message)
        .filter(Message.chat_room_id == room_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .all()
    )
    return list(reversed(msgs))


def _build_history(messages) -> list[dict]:
    history = []
    for m in messages:
        role = "assistant" if m.sender_role == "assistant" else "user"
        history.append({"role": role, "content": m.content})
    return history


def _is_personal_info_question(text: str) -> bool:
    t = (text or "").lower()
    keywords = [
        "my roll", "roll no", "roll number",
        "my id", "student id", "neura id",
        "my name", "who am i",
        "my department", "my dept", "my section", "my series",
        "tell me my roll", "tell me my roll no",
    ]
    return any(k in t for k in keywords)


BLOCKED_PROMPT = """
You are NEURA-RUET AI and a RUET academic assistant.

You must refuse in TWO cases:
(A) Unrelated/general knowledge questions (sports, celebrities, world facts, etc.)
(B) Personal/profile info requests (roll number, student id, name, dept/section/series)

Rules:
- Do NOT mention any product/app name.
- Do NOT mention the word 'Neura'.
- Do NOT provide facts about unrelated questions.
- Do NOT reveal any personal/profile info.
- Keep it short and polite.
- Redirect the user to RUET help: materials, notices, results/marks, cover pages, app usage.

Few-shot examples:

Example 1 (unrelated):
User: "who is Messi?"
Assistant: "I can’t help with general knowledge. I can help with RUET materials, notices, results/marks, cover pages, and app usage."

Example 2 (personal info):
User: "tell me my roll no"
Assistant: "I can’t access or share personal profile information here. I can help you with RUET materials, notices, results/marks, cover pages, and app usage."

Example 3 (personal info):
User: "what is my department and series?"
Assistant: "I can’t access or share personal profile information here. I can help you with RUET materials, notices, results/marks, cover pages, and app usage."

Now respond to the user.
""".strip()


def run_tool_and_get_assistant_text(
    *,
    db: Session,
    room_id: str,
    tool_name: str,
    user_text: str,
    student_obj,
    llm: LLMClient,
):
    # 1) fetch recent history
    last_msgs = _fetch_last_messages(db, room_id=room_id, limit=6)
    messages_history = _build_history(last_msgs)

    # 2) student profile context (used only for tool pipeline defaults)
    profile = {
        "neura_id": getattr(student_obj, "neura_id", None),
        "full_name": getattr(student_obj, "full_name", None),
        "roll_no": getattr(student_obj, "roll_no", None),
        "dept": getattr(student_obj, "dept", None),
        "section": getattr(student_obj, "section", None),
        "series": getattr(student_obj, "series", None),
    }

    # 3) conversation gate (LLM): decide chat vs tool vs blocked
    available_tools = list(TOOL_REGISTRY.keys())
    decision = route_intent(
        llm=llm,
        user_text=user_text,
        available_tools=available_tools,
    )

    # ✅ Force "personal info questions" into blocked behavior (even if router misroutes)
    personal_info = _is_personal_info_question(user_text)

    # 3A) blocked OR personal-info -> refuse + redirect
    if getattr(decision, "intent", None) == "blocked" or personal_info:
        refusal = llm.complete(
            system_prompt=BLOCKED_PROMPT,
            messages=[*messages_history, {"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.4,
        )
        return {"direct_text": refusal}

    # 3B) normal RUET/app chat -> reply normally (scope-limited)
    if getattr(decision, "intent", None) in ("general_chat", "neura_chat"):
        direct_text = llm.complete(
            system_prompt=(
                "You are a RUET academic assistant. Reply naturally and briefly. "
                "You can help with: finding materials (class notes, lecture slides, CT questions, semester questions), "
                "notices, results/marks, cover page generation, and app usage. "
                "Do NOT mention any product/app name. Do NOT mention the word 'Neura'. "
                "If the user asks unrelated/general knowledge, politely refuse and redirect to RUET help."
            ),
            messages=[*messages_history, {"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.6,
        )
        return {"direct_text": direct_text}

    # 4) gate wants a tool: prefer decision.tool_name, else frontend tool_name
    selected_tool_name = getattr(decision, "tool_name", None) or tool_name
    tool = get_tool(selected_tool_name)

    # 5) build context message for planner LLM
    context_user_message = {
        "role": "user",
        "content": json.dumps(
            {
                "student_profile": profile,
                "user_message": user_text,
                "notes": [
                    "Prefer using student_profile dept/section/series as defaults if user doesn't mention them."
                ],
            },
            ensure_ascii=False,
        ),
    }

    # 6) planner LLM call (JSON)
    raw = llm.complete(
        system_prompt=tool.system_prompt,
        messages=[*messages_history, context_user_message],
        json_mode=True,
        temperature=0.1,
    )

    # 7) parse JSON robustly
    try:
        data = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM did not return JSON")
        data = json.loads(raw[start : end + 1])

    # 8) sanitizers (robust against common LLM mistakes)
    if isinstance(data.get("year"), str):
        data["year"] = int(data["year"]) if data["year"].strip().isdigit() else None

    if isinstance(data.get("ct_no"), str):
        data["ct_no"] = int(data["ct_no"]) if data["ct_no"].strip().isdigit() else None

    if isinstance(data.get("series"), str):
        s = data["series"].strip()
        if s.isdigit():
            data["series"] = s

    # 9) validate into schema (and handle common planner mistakes gracefully)
    try:
        output = tool.output_model.model_validate(data)
    except ValidationError as e:
        errs = e.errors()
        material_type_err = any(
            err.get("loc") == ("material_type",) and err.get("type") in ("enum", "literal_error")
            for err in errs
        )
        if material_type_err:
            return {
                "direct_text": (
                    "I can’t do that with material search. "
                    "This tool is only for finding class notes, slides, CT questions, or semester questions. "
                    "Try asking for a material like: “CSE-2100 lecture slide on tree”."
                )
            }
        return {
            "direct_text": (
                "I couldn’t understand that request for material search. "
                "Please try again with a course code/name and what you need (notes/slides/CT/semester)."
            )
        }

    # 🔒 force dept + series from logged-in student profile (never trust LLM/user)
    output = _normalize_group_fields(output, profile)

    # 10) clarification path (planner asks)
    if getattr(output, "mode", None) == "ask":
        return {
            "needs_clarification": True,
            "question": output.question,
            "suggested_fields": output.missing_fields,
            "confidence": output.confidence,
        }

    # 11) run tool handler (DB)
    result = tool.handler(db=db, parsed=output, student_profile=profile)
    print("TOOL HANDLER RESULT:", result)

    return result
