# Router aggregator
from fastapi import APIRouter
from app.api.v1.endpoints.auth import student_auth_router
from app.api.v1.endpoints.auth import teacher_auth_router
from app.api.v1.endpoints.auth import cr_auth_router
from app.api.v1.endpoints.chat import student_chat_router
from app.api.v1.endpoints.chat import teacher_chat_router
from app.api.v1.endpoints.chat import cr_chat_router
from app.api.v1.endpoints.result_sheet import sheet_generator_routers
from app.api.v1.endpoints.notice_upload import teacher_notice_router
from app.api.v1.endpoints.notice_upload import cr_notice_router
from app.api.v1.endpoints.notice_upload import student_notice_router


api_router = APIRouter()

api_router.include_router(student_auth_router.router)
api_router.include_router(teacher_auth_router.router)
api_router.include_router(cr_auth_router.router)
api_router.include_router(student_chat_router.router)
api_router.include_router(teacher_chat_router.router)
api_router.include_router(cr_chat_router.router)
api_router.include_router(sheet_generator_routers.router)
api_router.include_router(teacher_notice_router.router)
api_router.include_router(cr_notice_router.router)
api_router.include_router(student_notice_router.router)