# Chat service
from app.models.chat import Chat

def create_chat(user_id: int, message: str):
    chat = Chat(user_id=user_id, message=message)
    return chat