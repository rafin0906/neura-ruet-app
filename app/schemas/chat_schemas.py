from pydantic import BaseModel
from typing import Optional
from datetime import datetime   

class ChatRoomCreateIn(BaseModel):
    title: Optional[str] = None


class ChatRoomOut(BaseModel):
    id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageCreateIn(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    chat_room_id: int
    sender_role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
