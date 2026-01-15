from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic_settings import BaseSettings

from dotenv import load_dotenv
load_dotenv()


from app.db.database import engine
from app.db.database import Base
from app.models.student_models import Student
from app.models.teacher_models import Teacher
from app.models.cr_models import CR
from app.models.ct_question_models import CTQuestion
from app.models.semester_question_models import SemesterQuestion
from app.models.lecture_slide_models import LectureSlide
from app.models.class_note_models import ClassNote
from app.models.notice_models import Notice
from app.api.v1.api import api_router

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Include the API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI app!"}

@app.get("/ping")
def read_root():
    return {"message": "route ping successful!"}
