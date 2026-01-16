from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.chat_room_models import ChatRoom, SenderRole
from app.models.message_models import Message
from app.models.student_models import Student
from app.schemas.chat_schemas import (
    ChatRoomCreateIn,
    ChatRoomOut,
    MessageCreateIn,
    MessageOut,
)
from app.services.dependencies import get_current_student
from app.services.chat_service import _get_student_room_or_404

router = APIRouter(prefix="/students/chat", tags=["Student Chat"])


@router.post("/rooms", response_model=ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: ChatRoomCreateIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    room = ChatRoom(
        owner_role=SenderRole.student,
        owner_student_id=str(student.id),   # force str
        title=payload.title,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms", response_model=List[ChatRoomOut])
def list_rooms(
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    rooms = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.owner_role == SenderRole.student,
            ChatRoom.owner_student_id == str(student.id),
        )
        .order_by(ChatRoom.updated_at.desc())
        .all()
    )
    return rooms


@router.get("/rooms/{room_id}/messages", response_model=List[MessageOut])
def get_room_messages(
    room_id: str,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    _get_student_room_or_404(db, room_id, str(student.id))

    msgs = (
        db.query(Message)
        .filter(Message.chat_room_id == room_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return msgs


@router.post("/rooms/{room_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    room_id: str,
    payload: MessageCreateIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    room = _get_student_room_or_404(db, room_id, str(student.id))

    tool_name = payload.tool_name  # currently unused

    msg = Message(
        chat_room_id=room.id,                # str
        sender_role=SenderRole.student,
        sender_student_id=str(student.id),   # str
        content=payload.content,
    )
    db.add(msg)

    room.updated_at = datetime.utcnow()
    db.add(room)

    db.commit()
    db.refresh(msg)
    return msg
