import json
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.ai.tool_registry import get_tool
from app.ai.llm_client import LLMClient
from app.models.message_models import Message  # adjust import if different

# you already have get_current_student dependency; you will pass student object here


def _fetch_last_messages(db: Session, room_id: str, limit: int = 6):
    msgs = (
        db.query(Message)
        .filter(Message.chat_room_id == room_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .all()
    )
    # reverse to chronological
    return list(reversed(msgs))


def _build_history(messages) -> list[dict]:
    history = []
    for m in messages:
        # map your enum/role values to LLM roles
        # assuming: m.sender_role in {"student","assistant","teacher","cr"}
        role = "assistant" if m.sender_role == "assistant" else "user"
        history.append({"role": role, "content": m.content})
    return history


def run_tool_and_get_assistant_text(
    *,
    db: Session,
    room_id: str,
    tool_name: str,
    user_text: str,
    student_obj,
    llm: LLMClient,
):
    # 4) fetch last 6 messages
    last_msgs = _fetch_last_messages(db, room_id=room_id, limit=6)

    # 5) store them in messages_history
    messages_history = _build_history(last_msgs)

    # print("\n===== MESSAGES HISTORY =====")
    # for msg in messages_history:
    #     print(f"{msg['role'].upper()}: {msg['content']}")

    # 6) student profile data (from dependency)
    profile = {
        "neura_id": getattr(student_obj, "neura_id", None),
        "full_name": getattr(student_obj, "full_name", None),
        "roll_no": getattr(student_obj, "roll_no", None),
        "dept": getattr(student_obj, "dept", None),
        "section": getattr(student_obj, "section", None),
        "series": getattr(student_obj, "series", None),
    }

    # 7) append history + profile into context
    # (we pass it into the user message so model can use defaults)
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

    # 8) tool based dynamic system prompt
    tool = get_tool(tool_name)

    # 9) send to llm and get response
    raw = llm.complete(
        system_prompt=tool.system_prompt,
        messages=[*messages_history, context_user_message],
        json_mode=True,          #  planner needs json
        temperature=0.1,
    )



    # 9.5) parse/validate strict json
    try:
        data = json.loads(raw)
    except Exception:
        # if model returned dirty text, try a hard cleanup strategy
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM did not return JSON")
        data = json.loads(raw[start : end + 1])

    output = tool.output_model.model_validate(data)


        # 👇 ADD THIS HERE
    if output.mode == "ask":
        return {
            "needs_clarification": True,
            "question": output.question,
            "suggested_fields": output.missing_fields,
            "confidence": output.confidence,
        }


    # 9.6) run tool handler (db query)
    result = tool.handler(db=db, parsed=output, student_profile=profile)

    print("TOOL HANDLER RESULT:", result)
    # 11) return response (role handled in message save outside)
    return result
