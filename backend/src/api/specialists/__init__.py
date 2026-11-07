from fastapi import APIRouter

from src.api.specialists.appointments import router as appointments_router
from src.api.specialists.client_notes import router as client_notes_router
from src.api.specialists.clients import router as clients_router
from src.api.specialists.free_slots import router as free_slots_router
from src.api.specialists.profile import router as profile_router
from src.api.specialists.slots import router as slots_router
from src.api.specialists.working_hours import router as working_hours_router

router = APIRouter()

router.include_router(profile_router, prefix="/profile")
router.include_router(appointments_router, prefix="/appointments")
router.include_router(clients_router, prefix="/clients")
router.include_router(client_notes_router, prefix="/clients")
router.include_router(working_hours_router, prefix="/template")
router.include_router(slots_router, prefix="/slots")
# free_slots has /{specialist_id}/free-slots path - no prefix
router.include_router(free_slots_router)
