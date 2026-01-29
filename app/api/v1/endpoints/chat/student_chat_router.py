from datetime import datetime
from typing import List
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.database import get_db
from app.models.chat_room_models import ChatRoom, SenderRole
from app.models.message_models import Message
from app.models.student_models import Student
from app.schemas.backend_schemas.chat_schemas import (
    ChatRoomCreateIn,
    ChatRoomOut,
    MessageCreateIn,
    MessageOut,
)
from app.services.dependencies import get_current_student
from app.services.chat_service import _get_student_room_or_404

from app.ai.tool_registry import get_tool
from app.ai.llm_client import llm_client
from app.services.ai_chat_service import run_tool_and_get_assistant_text
from app.services.answer_llm_service import build_answer_prompt


router = APIRouter(prefix="/students/chat", tags=["Student Chat"])


@router.post("/rooms", response_model=ChatRoomOut, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: ChatRoomCreateIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    room = ChatRoom(
        owner_role=SenderRole.student,
        owner_student_id=str(student.id),
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


@router.post(
    "/rooms/{room_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    room_id: str,
    payload: MessageCreateIn,
    db: Session = Depends(get_db),
    student: Student = Depends(get_current_student),
):
    room = _get_student_room_or_404(db, room_id, str(student.id))

    tool_name = payload.tool_name
    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    try:
        get_tool(tool_name)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

    # 1) save student message
    student_msg = Message(
        chat_room_id=room.id,
        sender_role=SenderRole.student,
        sender_student_id=str(student.id),
        content=payload.content,
    )
    db.add(student_msg)
    room.updated_at = datetime.utcnow()
    db.add(room)
    db.commit()
    db.refresh(student_msg)

    # 2) planner tool pipeline (LLM JSON -> DB search bundle OR clarification)
    try:
        result_payload = run_tool_and_get_assistant_text(
            db=db,
            room_id=room.id,
            tool_name=tool_name,
            user_text=payload.content,
            student_obj=student,
            llm=llm_client,
        )
    except (ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

    # 3) build final assistant answer (do NOT save planner JSON)
    if isinstance(result_payload, dict) and result_payload.get("needs_clarification"):
        assistant_text = result_payload.get("question") or "Please provide more details."
    else:
        system_prompt, messages = build_answer_prompt(result_payload)

        assistant_text = llm_client.complete(
            system_prompt=system_prompt,
            messages=messages,
            json_mode=False,     #  natural language
            temperature=0.7,
        )

    # 4) save only final answer
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
