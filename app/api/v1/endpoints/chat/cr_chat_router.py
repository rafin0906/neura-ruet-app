from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.chat_room_models import ChatRoom, SenderRole
from app.models.message_models import Message
from app.models.cr_models import CR
from app.schemas.backend_schemas.chat_schemas import (
    ChatRoomCreateIn,
    ChatRoomOut,
    MessageCreateIn,
    MessageOut,
)
from app.services.dependencies import get_current_cr
from app.services.chat_service import _get_cr_room_or_404

router = APIRouter(prefix="/crs/chat", tags=["CR Chat"])


@router.post("/rooms", response_model=ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: ChatRoomCreateIn,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    room = ChatRoom(
        owner_role=SenderRole.cr,
        owner_cr_id=str(cr.id),
        title=payload.title,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms", response_model=List[ChatRoomOut])
def list_rooms(
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    rooms = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.owner_role == SenderRole.cr,
            ChatRoom.owner_cr_id == str(cr.id),
        )
        .order_by(ChatRoom.updated_at.desc())
        .all()
    )
    return rooms


@router.get("/rooms/{room_id}/messages", response_model=List[MessageOut])
def get_room_messages(
    room_id: str,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    _get_cr_room_or_404(db, room_id, str(cr.id))

    msgs = (
        db.query(Message)
        .filter(Message.chat_room_id == room_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return msgs


@router.post(
    "/rooms/{room_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    room_id: str,
    payload: MessageCreateIn,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    room = _get_cr_room_or_404(db, room_id, str(cr.id))

    msg = Message(
        chat_room_id=room.id,
        sender_role=SenderRole.cr,
        sender_cr_id=str(cr.id),
        content=payload.content,
    )
    db.add(msg)

    room.updated_at = datetime.utcnow()
    db.add(room)

    db.commit()
    db.refresh(msg)
    return msg
