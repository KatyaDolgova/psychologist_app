from datetime import datetime

from sqlalchemy import func, select

from src.core.wrapper import handle_db_errors
from src.crud.impl.base import BaseDAO
from src.models.lesson import Lesson
from src.models.lesson_participant import LessonParticipant
from src.models.lesson_transcript import LessonTranscript


class LessonDAO(BaseDAO):
    """DAO для уроков."""

    model = Lesson

    @handle_db_errors
    async def find_by_teacher(self, teacher_id: int, limit: int, offset: int):
        """Уроки автора вместе со статусом транскрипта, новые сверху."""
        query = (
            select(Lesson, LessonTranscript.status)
            .outerjoin(LessonTranscript, LessonTranscript.lesson_id == Lesson.id)
            .where(Lesson.teacher_id == teacher_id)
            .order_by(Lesson.created_at.desc(), Lesson.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.all()

    @handle_db_errors
    async def uploaded_since(
        self, teacher_id: int, since: datetime
    ) -> tuple[int, datetime | None]:
        """Сколько байт автор загрузил начиная с since и когда была самая ранняя загрузка."""
        query = select(
            func.coalesce(func.sum(Lesson.audio_size_bytes), 0),
            func.min(Lesson.created_at),
        ).where(Lesson.teacher_id == teacher_id, Lesson.created_at >= since)
        total, oldest = (await self.session.execute(query)).one()
        return int(total), oldest

    @handle_db_errors
    async def find_shared_with(self, user_id: int, limit: int, offset: int):
        """Уроки, которыми с пользователем поделились, со статусом транскрипта."""
        query = (
            select(Lesson, LessonTranscript.status)
            .join(LessonParticipant, LessonParticipant.lesson_id == Lesson.id)
            .outerjoin(LessonTranscript, LessonTranscript.lesson_id == Lesson.id)
            .where(LessonParticipant.user_id == user_id)
            .order_by(Lesson.created_at.desc(), Lesson.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.all()
