from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


# -------- ChatRoom --------

class ChatRoomCreateIn(BaseModel):
    title: Optional[str] = None


class ChatRoomOut(BaseModel):
    id: UUID

    owner_role: str
    owner_student_id: Optional[UUID] = None
    owner_teacher_id: Optional[UUID] = None
    owner_cr_id: Optional[UUID] = None

    title: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -------- Message --------

class MessageCreateIn(BaseModel):
    tool_name: str
    content: str


class MessageOut(BaseModel):
    id: UUID
    chat_room_id: UUID

    sender_role: str
    sender_student_id: Optional[UUID] = None
    sender_teacher_id: Optional[UUID] = None
    sender_cr_id: Optional[UUID] = None

    content: str

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
