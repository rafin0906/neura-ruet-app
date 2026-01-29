from enum import Enum
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, ConfigDict


class MaterialType(str, Enum):
    class_note = "class_note"
    ct_question = "ct_question"
    lecture_slide = "lecture_slide"
    semester_question = "semester_question"


class MatchMode(str, Enum):
    exact = "exact"
    contains = "contains"


class SortBy(str, Enum):
    newest = "newest"
    oldest = "oldest"


class QueryMode(str, Enum):
    query = "query"   # run DB query now
    ask = "ask"       # ask user for more info


class FindMaterialsLLMOutput(BaseModel):
    """
    STRICT output JSON the LLM must return for 'find_materials'.
    """

    model_config = ConfigDict(extra="forbid")

    tool: Literal["find_materials"] = "find_materials"

    # 🔑 decision field
    mode: QueryMode = QueryMode.query

    # used only when mode == "ask"
    question: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)

    # -------------------------
    # Filters (ALL optional)
    # -------------------------
    material_type: MaterialType

    course_code: Optional[str] = None
    course_name: Optional[str] = None

    dept: Optional[str] = None
    sec: Optional[str] = None
    series: Optional[str] = None

    # class_note / lecture_slide
    topic: Optional[str] = None

    # class_note only
    written_by: Optional[str] = None

    # ct_question only
    ct_no: Optional[int] = None

    # semester_question only
    year: Optional[int] = None

    # -------------------------
    # Query behavior
    # -------------------------
    match_mode: MatchMode = MatchMode.contains
    limit: int = Field(10, ge=1, le=50)
    offset: int = Field(0, ge=0)
    sort_by: SortBy = SortBy.newest

    confidence: float = Field(0.7, ge=0.0, le=1.0)
