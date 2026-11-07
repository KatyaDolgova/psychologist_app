from pydantic import BaseModel

from src.models.enums import MethodFormat


class FavoritesSpecialistsResponse(BaseModel):
    """Схема ответа получения избранных специалистов пользователя"""

    id: int
    avatar: str | None
    full_name: str
    methods: list[MethodFormat]


class SpecialistID(BaseModel):
    """Схема для запроса добавления/удаления специалиста из избранных"""

    id: int
