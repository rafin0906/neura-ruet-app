from dataclasses import dataclass
from typing import Type, Callable, Any

from pydantic import BaseModel

from app.schemas.ai_schemas.find_materials_schemas import FindMaterialsLLMOutput


@dataclass(frozen=True)
class ToolSpec:
    name: str
    system_prompt: str
    output_model: Type[BaseModel]
    handler: Callable[..., Any]


def build_find_materials_system_prompt() -> str:
    return """
You are NeuraRUET AI. The user has already selected the tool: find_materials.

You must output ONLY ONE JSON object that matches the schema (no markdown, no extra text).

Key behavior:
- All filter fields are optional. Use whatever the user provides.
- Decide whether to search now or ask for more info.

Decision rule (IMPORTANT):
- Use mode="query" when the user gave enough information to search.
  Enough info means at least ONE strong filter, or TWO medium filters:
  Strong filters: course_code, ct_no, year
  Medium filters: topic, written_by, course_name
  Group filters: dept/sec/series are NOT strong by themselves.
- Use mode="ask" when the request is too broad or ambiguous (likely to match many things),
  OR when the user message has no meaningful filter (e.g., only "give class note"),
  OR when the topic is very generic (e.g., "DSA", "Math") without any course reference.
  In ask mode, provide:
  - question: a short question to the user
  - missing_fields: suggested fields (not mandatory)

Matching rules:
- match_mode="exact" when user gives exact code/year/ct_no (e.g., CSE-2100, CT 1, 2021).
- match_mode="contains" for partial text like topic or written_by.

Field constraints:
- written_by is ONLY for class_note.
- ct_no ONLY for ct_question.
- year ONLY for semester_question.

Field map (MUST follow):
- Always allowed for ALL: course_code, course_name, dept, sec, series
- class_note allowed: topic, written_by
- lecture_slide allowed: topic
- ct_question allowed: ct_no
- semester_question allowed: year

IMPORTANT:
- If the user says a topic-like word for ct_question (e.g., "dc motor"), put it in course_name (NOT topic).
- If the user says a topic-like word for semester_question, put it in course_name (NOT topic).
- Never output fields that are not allowed for that material_type.


Output format rules:
- Always include: tool, mode, material_type, match_mode, limit, offset, sort_by, confidence, missing_fields.
- If mode="ask", you MUST include "question".

Few-shot examples:

Example A:
User: "CSE-2100 CT 1 for CSE C series 23"
Output:
{"tool":"find_materials","mode":"query","material_type":"ct_question","course_code":"CSE-2100","ct_no":1,"dept":"CSE","sec":"C","series":"23","match_mode":"exact","limit":10,"offset":0,"sort_by":"newest","confidence":0.92,"missing_fields":[]}

Example B:
User: "lecture slide on tree for cse-2100"
Output:
{"tool":"find_materials","mode":"query","material_type":"lecture_slide","course_code":"CSE-2100","topic":"tree","match_mode":"contains","limit":10,"offset":0,"sort_by":"newest","confidence":0.86,"missing_fields":[]}

Example C:
User: "class note on array written by Rafin"
Output:
{"tool":"find_materials","mode":"query","material_type":"class_note","topic":"array","written_by":"Rafin","match_mode":"contains","limit":10,"offset":0,"sort_by":"newest","confidence":0.84,"missing_fields":[]}

Example D (ask):
User: "give me class note"
Output:
{"tool":"find_materials","mode":"ask","material_type":"class_note","question":"Which course code/name or topic is the class note for? (e.g., CSE-2100 or Array)","match_mode":"contains","limit":10,"offset":0,"sort_by":"newest","confidence":0.55,"missing_fields":["course_code_or_name","topic"]}

Example E (generic topic, ask):
User: "class note on DSA"
Output:
{"tool":"find_materials","mode":"ask","material_type":"class_note","question":"DSA is broad—which course code or exact topic (e.g., Array/Tree/Sorting)?","match_mode":"contains","limit":10,"offset":0,"sort_by":"newest","confidence":0.58,"missing_fields":["course_code_or_name","topic"]}
""".strip()


# Registry (scalable: add new tools here later)
TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    TOOL_REGISTRY[spec.name] = spec


def get_tool(tool_name: str) -> ToolSpec:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name]

def init_tools() -> None:
    # Importing here avoids circular imports at module import time
    from app.ai.tools.find_materials import register_find_materials_tool
    register_find_materials_tool()
