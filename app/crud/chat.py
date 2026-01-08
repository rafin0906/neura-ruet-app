# Chat CRUD operations
from sqlalchemy.orm import Session
from app.models.chat import Chat

def get_chat_by_id(db: Session, chat_id: int):
    return db.query(Chat).filter(Chat.id == chat_id).first()

def create_chat(db: Session, chat: Chat):
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat