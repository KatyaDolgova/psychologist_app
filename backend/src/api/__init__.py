from fastapi import APIRouter

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api.calls import router as call_router
from src.api.chats import router as chat_router
from src.api.lessons import router as lesson_router
from src.api.specialists import router as specialists_router
from src.api.users import router as user_router

router = APIRouter(prefix="")

router.include_router(auth_router, prefix="/auth")
router.include_router(user_router, prefix="/user")
router.include_router(chat_router, prefix="/chats")
router.include_router(call_router, prefix="/calls")
router.include_router(lesson_router, prefix="/lessons")
router.include_router(admin_router, prefix="/admin")
router.include_router(specialists_router, prefix="/specialists")
