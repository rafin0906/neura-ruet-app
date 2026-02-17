from datetime import datetime
from typing import List
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.ai.llm_client import GroqClient
from app.services.ai_chat_service import run_tool_chat

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


def _auto_title_from_text(text: str, max_len: int = 60) -> str:
    text = " ".join((text or "").strip().split())
    if not text:
        return "New chat"
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"




@router.post("/rooms", response_model=ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: ChatRoomCreateIn,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    room = ChatRoom(
        owner_role=SenderRole.cr,
        owner_cr_id=str(cr.id),
        title=(payload.title.strip() if payload.title and payload.title.strip() else "New Chat"),
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
async def send_message(
    room_id: str,
    payload: MessageCreateIn,
    db: Session = Depends(get_db),
    cr: CR = Depends(get_current_cr),
):
    room = _get_cr_room_or_404(db, room_id, str(cr.id))

    if not payload.tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")
    
    ALLOWED_TOOLS = {"find_materials", "view_notices", "generate_cover_page", "check_marks"}
    
    if payload.tool_name not in ALLOWED_TOOLS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid tool. Allowed tools: {', '.join(ALLOWED_TOOLS)}"
        )

    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    user_text = payload.content.strip()

    existing_cr_msg = (
        db.query(Message)
        .filter(
            Message.chat_room_id == room.id,
            Message.sender_role == SenderRole.cr,
        )
        .first()
    )

    is_first_message = existing_cr_msg is None

    if is_first_message and room.title == "New Chat":
        room.title = _auto_title_from_text(user_text)
        db.add(room)

    cr_msg = Message(
        chat_room_id=room.id,
        sender_role=SenderRole.cr,
        sender_cr_id=str(cr.id),
        content=user_text,
    )
    db.add(cr_msg)

    room.updated_at = datetime.utcnow()
    db.add(room)
    db.commit()
    db.refresh(cr_msg)

    try:
        llm = GroqClient()

        assistant_text = await run_tool_chat(
            db=db,
            room_id=room.id,
            tool_name=payload.tool_name,
            student=cr,
            user_text=user_text,
            llm=llm,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    assistant_msg = Message(
        chat_room_id=room.id,
        sender_role=SenderRole.assistant,
        content=assistant_text,
    )
    db.add(assistant_msg)

    room.updated_at = datetime.utcnow()
    db.add(room)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg