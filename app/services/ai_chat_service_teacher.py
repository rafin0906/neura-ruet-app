from app.services.ai_chat_service import fetch_last_messages, to_llm_history, gate_intent
from app.ai.tool_registry import get_tool
from app.ai.sys_prompts import GENERAL_CHAT_PROMPT, BLOCKED_PROMPT

async def run_tool_chat_teacher(
    db,
    room_id: str,
    tool_name: str,
    teacher,
    user_text: str,
    llm,
) -> str:
    last_msgs = fetch_last_messages(db, room_id, limit=6)
    history = to_llm_history(last_msgs)

    intent, _ = await gate_intent(llm, user_text, history)

    if intent == "general_chat":
        return await llm.complete(
            system_prompt=GENERAL_CHAT_PROMPT,
            messages=history + [{"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.5,
            max_tokens=300,
        )

    if intent == "blocked":
        return await llm.complete(
            system_prompt=BLOCKED_PROMPT,
            messages=history + [{"role": "user", "content": user_text}],
            json_mode=False,
            temperature=0.2,
            max_tokens=220,
        )

    tool = get_tool(tool_name)

    # ✅ teacher passed (not student)
    return await tool.handler(
        db=db,
        room_id=room_id,
        teacher=teacher,
        user_text=user_text,
        history=history,
        llm=llm,
    )
