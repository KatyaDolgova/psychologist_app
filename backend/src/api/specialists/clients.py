from fastapi import APIRouter, Depends

from src.core.dependencies import get_current_specialist_id
from src.schemas.clients import ClientProfileForSpecialist, SpecialistClientSchema
from src.services.specialist_clients_service import SpecialistClientsService

router = APIRouter(tags=["Specialists Clients"])


@router.get(
    "/",
    summary="Get all clients",
    description="Получить список всех клиентов специалиста с информацией о сессиях",
)
async def get_clients(
    limit: int = 25,
    offset: int = 0,
    name: str | None = None,
    current_specialist: int = Depends(get_current_specialist_id),
    service: SpecialistClientsService = Depends(),
) -> list[SpecialistClientSchema]:
    return await service.get_clients(
        specialist_id=current_specialist,
        limit=limit,
        offset=offset,
        name=name,
    )


@router.get(
    "/{user_id}",
    summary="Get client profile",
    description="Получить профиль клиента по user_id",
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
        403: {
            "description": "Нет записей с этим клиентом",
            "content": {
                "application/json": {
                    "example": {"detail": "Нет записей с этим клиентом"}
                }
            },
        },
        404: {
            "description": "Клиент не найден",
            "content": {
                "application/json": {"example": {"detail": "Клиент не найден"}}
            },
        },
    },
)
async def get_client_profile(
    user_id: int,
    current_specialist: int = Depends(get_current_specialist_id),
    service: SpecialistClientsService = Depends(),
) -> ClientProfileForSpecialist:
    return await service.get_client_profile(
        specialist_id=current_specialist, user_id=user_id
    )
