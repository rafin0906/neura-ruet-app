from fastapi import FastAPI
from sqlalchemy.orm import Session
from pydantic_settings import BaseSettings


from app.core.database import engine
from app.core.database import Base
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.cr import CR

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI app!"}

