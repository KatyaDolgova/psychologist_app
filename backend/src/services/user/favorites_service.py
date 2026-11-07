from fastapi import Depends

from src.config import settings
from src.core.dependencies import get_store
from src.crud import Store
from src.schemas import FavoritesSpecialistsResponse


class FavoriteService:
    """
    Сервис для управления избранными специалистами клиента
    """

    def __init__(
        self,
        store: Store = Depends(get_store),
    ):
        """Инициализация избранных специалистами клиента

        Args:
            store: Хранилище данных, используемое для операций с избранными.
        """
        self._store = store

    async def get_user_favorites(self, user_id) -> list[FavoritesSpecialistsResponse]:
        specialists = await self._store.favorite.find_user_favorites(user_id=user_id)

        return [
            FavoritesSpecialistsResponse(
                id=specialist.id,
                full_name=f"{specialist.first_name} {specialist.last_name}",
                avatar=settings.STATIC_BASE_URL + specialist.avatar
                if specialist.avatar
                else None,
                methods=specialist.methods,
            )
            for specialist in specialists
        ]

    async def add_specialist_to_favorites(self, user_id: int, specialist_id: int):
        await self._store.specialist.check_exist_or_404(model_id=specialist_id)
        await self._store.favorite.add(user_id=user_id, specialist_id=specialist_id)

    async def delete_from_favorites(self, user_id: int, specialist_id: int):
        await self._store.favorite.delete_from_favorites(
            user_id=user_id, specialist_id=specialist_id
        )
