from datetime import datetime
from typing import List
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Body
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.chat_room_models import ChatRoom, SenderRole
from app.models.message_models import Message
from app.models.teacher_models import Teacher
from app.schemas.backend_schemas.chat_schemas import (
    ChatRoomCreateIn,
    ChatRoomOut,
    MessageCreateIn,
    MessageOut,
)
from app.services.dependencies import get_current_teacher
from app.services.chat_service import _get_teacher_room_or_404
from app.ai.llm_client import GroqClient
from app.services.ai_chat_service_teacher import run_tool_chat_teacher


router = APIRouter(prefix="/teachers/chat", tags=["Teacher Chat"])


def _auto_title_from_text(text: str, max_len: int = 60) -> str:
    text = " ".join((text or "").strip().split())
    if not text:
        return "New Chat"
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


@router.post("/rooms", response_model=ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: ChatRoomCreateIn = Body(default_factory=ChatRoomCreateIn),
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    room = ChatRoom(
        owner_role=SenderRole.teacher,
        owner_teacher_id=str(teacher.id),
        title=(payload.title.strip() if payload.title and payload.title.strip() else "New Chat"),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms", response_model=List[ChatRoomOut])
def list_rooms(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    rooms = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.owner_role == SenderRole.teacher,
            ChatRoom.owner_teacher_id == str(teacher.id),
        )
        .order_by(ChatRoom.updated_at.desc())
        .all()
    )
    return rooms


@router.get("/rooms/{room_id}/messages", response_model=List[MessageOut])
def get_room_messages(
    room_id: str,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    _get_teacher_room_or_404(db, room_id, str(teacher.id))

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
    teacher: Teacher = Depends(get_current_teacher),
):
    room = _get_teacher_room_or_404(db, room_id, str(teacher.id))

    if not payload.tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    # ✅ TEACHER-ONLY TOOLS
    ALLOWED_TOOLS = {
        "find_materials": "Find Materials",
        "generate_marksheet": "Generate Mark Sheet",
    }

    if payload.tool_name not in ALLOWED_TOOLS:
        allowed_tool_names = ", ".join(ALLOWED_TOOLS.values())
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tool. Allowed tools: {allowed_tool_names}",
        )


    if not payload.content or not payload.content.strip():
        raise HTTPException(status_code=400, detail="content is required")

    user_text = payload.content.strip()

    # auto-title on first message
    existing_teacher_msg = (
        db.query(Message)
        .filter(
            Message.chat_room_id == room.id,
            Message.sender_role == SenderRole.teacher,
        )
        .first()
    )

    is_first_message = existing_teacher_msg is None
    if is_first_message and room.title == "New Chat":
        room.title = _auto_title_from_text(user_text)
        db.add(room)

    teacher_msg = Message(
        chat_room_id=room.id,
        sender_role=SenderRole.teacher,
        sender_teacher_id=str(teacher.id),
        content=user_text,
    )
    db.add(teacher_msg)

    room.updated_at = datetime.utcnow()
    db.add(room)
    db.commit()
    db.refresh(teacher_msg)

    try:
        llm = GroqClient()

        assistant_text = await run_tool_chat_teacher(
            db=db,
            room_id=room.id,
            tool_name=payload.tool_name,
            teacher=teacher,   # 🔥 teacher context
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
