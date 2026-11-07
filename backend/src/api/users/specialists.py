from fastapi import APIRouter, Depends

from src.core.dependencies import get_current_user_id
from src.schemas.specialists import SpecialistResponse
from src.services.user.specialists import SpecialistsService

router = APIRouter(tags=["Specialists"])


@router.get(
    "/",
    summary="Get all specialists",
    description="Получить список всех специалистов",
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
    },
)
async def get_all_specialists(
    _: int = Depends(get_current_user_id),
    service: SpecialistsService = Depends(),
) -> list[SpecialistResponse]:
    return await service.get_all_specialists()
