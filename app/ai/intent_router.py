import json
from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class RouteDecision(BaseModel):
    intent: Literal["use_tool", "neura_chat", "blocked"]
    tool_name: Optional[str] = None
    confidence: float = Field(ge=0, le=1, default=0.5)
    reason: Optional[str] = None



def build_router_prompt(available_tools: list[str]) -> str:
    return f"""
You are a routing system for a RUET academic assistant.

The assistant is ONLY allowed to help with RUET academic and student-app related topics:
- class notes, lecture slides
- CT questions, semester questions
- notices
- academic results
- how to use the RUET student app
- short greetings and polite conversation

If the user asks anything NOT related to RUET academics or student app usage
(for example: sports, celebrities, world facts, general knowledge like "who is Messi"),
set intent="blocked".

Return ONLY JSON:
{{
  "intent": "use_tool" | "neura_chat" | "blocked",
  "tool_name": string | null,
  "confidence": number,
  "reason": string | null
}}

Rules:
- Greetings or polite conversation → intent="neura_chat".
- RUET academic requests that need database access → intent="use_tool"
  and choose tool_name from:
{available_tools}
- Anything unrelated to RUET → intent="blocked".

Examples:
User: "hi"
Output: {{"intent":"neura_chat","tool_name":null,"confidence":0.95,"reason":"greeting"}}

User: "class note on tree"
Output: {{"intent":"use_tool","tool_name":"find_materials","confidence":0.9,"reason":"ruet academic material search"}}

User: "who is Messi?"
Output: {{"intent":"blocked","tool_name":null,"confidence":0.98,"reason":"not ruet related"}}
""".strip()



def route_intent(*, llm, user_text: str, available_tools: list[str]) -> RouteDecision:
    system_prompt = build_router_prompt(available_tools)
    raw = llm.complete(
        system_prompt=system_prompt,
        messages=[{"role": "user", "content": user_text}],
        json_mode=True,
        temperature=0.0,
    )

    data = json.loads(raw) if isinstance(raw, str) else raw
    return RouteDecision.model_validate(data)
