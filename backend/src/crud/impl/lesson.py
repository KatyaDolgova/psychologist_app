from src.crud.impl.base import BaseDAO
from src.models.lesson import Lesson


class LessonDAO(BaseDAO):
    """DAO для уроков."""

    model = Lesson
