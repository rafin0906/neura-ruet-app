# Router aggregator
from fastapi import APIRouter
from app.api.v1.endpoints import students_router
from app.api.v1.endpoints import teachers_router
from app.api.v1.endpoints import cr_router
from app.api.v1.endpoints import student_chat_router

api_router = APIRouter()

api_router.include_router(students_router.router)
api_router.include_router(teachers_router.router)
api_router.include_router(cr_router.router)
api_router.include_router(student_chat_router.router)