from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.chat_room_models import ChatRoom, SenderRole

def _get_cr_room_or_404(db: Session, room_id: str, cr_id: str) -> ChatRoom:
    room = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.id == room_id,
            ChatRoom.owner_role == SenderRole.cr,
            ChatRoom.owner_cr_id == cr_id,
        )
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return room




def _get_student_room_or_404(db: Session, room_id: str, student_id: str) -> ChatRoom:
    room = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.id == room_id,
            ChatRoom.owner_role == SenderRole.student,
            ChatRoom.owner_student_id == student_id,
        )
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return room


def _get_teacher_room_or_404(db: Session, room_id: str, teacher_id: str) -> ChatRoom:
    room = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.id == room_id,
            ChatRoom.owner_role == SenderRole.teacher,
            ChatRoom.owner_teacher_id == teacher_id,
        )
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return room
