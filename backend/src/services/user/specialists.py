from fastapi import Depends

from src.config import settings
from src.core.dependencies import get_store
from src.crud import Store
from src.schemas.specialists import SpecialistResponse


class SpecialistsService:
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

    async def get_all_specialists(self):
        data = await self._store.specialist.find_all()
        return [
            SpecialistResponse(
                id=specialist.id,
                matches_count=3,
                first_name=specialist.first_name,
                last_name=specialist.last_name,
                methods=specialist.methods,
                avatar=settings.STATIC_BASE_URL + specialist.avatar
                if specialist.avatar
                else None,
                experience=specialist.experience,
                price=specialist.price,
                rating=specialist.rating,
            )
            for specialist in data
            if specialist.first_name and specialist.last_name
        ]
