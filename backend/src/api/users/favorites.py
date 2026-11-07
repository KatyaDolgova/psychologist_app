from fastapi import APIRouter, Depends

from src.core.dependencies import get_current_user_id
from src.schemas import EmptyModel, FavoritesSpecialistsResponse, SpecialistID
from src.services.user.favorites_service import FavoriteService

router = APIRouter(tags=["Favorites"])


@router.get(
    "/",
    summary="Get profile favorites specialists",
    description="Получить избранных специалистов пользователя",
    response_model=list[FavoritesSpecialistsResponse],
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
    },
)
async def get_user_favorites(
    user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(),
):
    return await service.get_user_favorites(user_id=user_id)


@router.post(
    "/",
    summary="Add specialist to favorites",
    description="Добавить специалиста в избранное",
    response_model=EmptyModel,
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
        404: {
            "description": "Ресурс не найден",
            "content": {
                "application/json": {"example": {"detail": "Ресурс не найден"}}
            },
        },
        409: {
            "description": "Специалист уже добавлен в избранное",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Конфликт данных: нарушение ограничений целостности"
                    }
                }
            },
        },
    },
)
async def add_specialist_to_favorites(
    data: SpecialistID,
    user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(),
):
    await service.add_specialist_to_favorites(user_id=user_id, specialist_id=data.id)
    return {}


@router.delete(
    "/{specialist_id}/",
    summary="Delete specialist from favorites",
    description="Удалить специалиста из избранных",
    status_code=204,
    responses={
        401: {
            "description": "Токен не валиден",
            "content": {
                "application/json": {"example": {"detail": "Токен не валиден"}}
            },
        },
        404: {
            "description": "Ресурс не найден",
            "content": {
                "application/json": {"example": {"detail": "Ресурс не найден"}}
            },
        },
    },
)
async def delete_from_favorites(
    specialist_id: int,
    user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(),
):
    return await service.delete_from_favorites(
        user_id=user_id, specialist_id=specialist_id
    )
