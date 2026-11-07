from fastapi import APIRouter, Depends

from src.core.dependencies import get_current_specialist_id
from src.schemas.appointments import AppointmentSchema
from src.services.user.appointments import AppointmentService

router = APIRouter(tags=["Specialists Appointments"])


@router.get(
    "/",
    summary="Get appointments",
    description="Получить список всех записей",
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
    },
)
async def get_all_appointments(
    limit: int = 25,
    offset: int = 0,
    is_upcoming: bool = True,
    client_id: int | None = None,
    current_specialist: int = Depends(get_current_specialist_id),
    service: AppointmentService = Depends(),
) -> list[AppointmentSchema]:
    return await service.get_specialist_appointments(
        limit=limit,
        offset=offset,
        specialist_id=current_specialist,
        is_upcoming=is_upcoming,
        client_id=client_id,
    )
