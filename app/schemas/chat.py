# Chat schema
from pydantic import BaseModel

class ChatBase(BaseModel):
    message: str

class ChatCreate(ChatBase):
    user_id: int

class ChatResponse(ChatBase):
    id: int

    class Config:
        orm_mode = True