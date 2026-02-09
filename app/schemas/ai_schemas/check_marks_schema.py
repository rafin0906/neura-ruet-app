from pydantic import BaseModel
from typing import Optional, List, Literal

class CheckMarksExtracted(BaseModel):
    mode: Literal["ok", "ask", "wrong_tool"] = "ok"
    course_code: str = ""
    ct_no: Optional[int] = None

    # for ask
    question: Optional[str] = None
    missing_fields: List[str] = []

    # for wrong_tool
    message: Optional[str] = None
