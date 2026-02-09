# app/services/ai_chat_service.py

import json
from typing import Dict, List, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.message_models import Message
from app.ai.llm_client import GroqClient
from app.ai.tool_registry import get_tool
from app.ai.sys_prompts import (
    TOOL_GATE_JSON_PROMPT,
    GENERAL_CHAT_PROMPT,
    BLOCKED_PROMPT,
)


def fetch_last_messages(db: Session, room_id: str, limit: int = 6) -> List[Message]:
    msgs = (
        db.query(Message)
        .filter(Message.chat_room_id == room_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
        .all()
    )
    return list(reversed(msgs))


def to_llm_history(msgs: List[Message]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for m in msgs:
        role = "assistant" if m.sender_role == "assistant" else "user"
        out.append({"role": role, "content": m.content})
    return out


async def gate_intent(llm: GroqClient, user_text: str, history: List[Dict[str, str]]) -> Tuple[str, str]:
    raw = await llm.complete(
        system_prompt=TOOL_GATE_JSON_PROMPT,
        messages=history + [{"role": "user", "content": user_text}],
        json_mode=True,
        temperature=0.1,
        max_tokens=200,
    )
    try:
        data = json.loads(raw)
        intent = data.get("intent")
        reason = data.get("reason", "")
        if intent not in ("general_chat", "blocked", "tool_query"):
            return "tool_query", "fallback"
        return intent, reason
    except Exception:
        return "tool_query", "fallback"


async def run_tool_chat(
    db: Session,
    room_id: str,
    tool_name: str,
    student=None,
    cr=None,
    user_text: str = "",
    llm: GroqClient = None,
) -> str:
    """
    Common entrypoint for all tools.
    - uses memory
    - gates intent
    - routes to: general_chat / blocked / tool handler
    """
    user = cr if cr else student
    if not user:
        return "Error: No user context provided."

    last_msgs = fetch_last_messages(db, room_id, limit=6)
    history = to_llm_history(last_msgs)

    intent, _reason = await gate_intent(llm, user_text, history)

    # 1) general chat
    if intent == "general_chat":
        return await llm.complete(
            system_prompt=GENERAL_CHAT_PROMPT,
            messages=history + [{"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.5,
            max_tokens=300,
        )

    # 2) blocked
    if intent == "blocked":
        return await llm.complete(
            system_prompt=BLOCKED_PROMPT,
            messages=history + [{"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.2,
            max_tokens=220,
        )

    # 3) tool query -> run the tool
    tool = get_tool(tool_name)

    # Handlers can use history too, so pass it in
    result = await tool.handler(
        db=db,
        room_id=room_id,
        student=user,
        user_text=user_text,
        history=history,
        llm=llm,
    )
    return result