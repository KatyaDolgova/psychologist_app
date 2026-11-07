from sqlalchemy import select

from src.crud.impl.base import BaseDAO
from src.models import SpecialistProfile


class SpecialistDAO(BaseDAO):
    """
    DAO для работы с специалистами.

    Предоставляет методы для управления специалистами, проверки
    их статуса, создания новых специалистов и получения информации.
    """

    model = SpecialistProfile

    async def get_name_and_avatar(self, user_id: int):
        query = select(
            self.model.first_name, self.model.last_name, self.model.avatar
        ).filter_by(id=user_id)
        result = await self.session.execute(query)
        return result.mappings().one_or_none()
