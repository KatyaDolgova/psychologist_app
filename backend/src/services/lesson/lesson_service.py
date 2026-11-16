import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, UploadFile

from src.config import settings
from src.core.dependencies import get_store
from src.core.exceptions import (
    AudioFileMissingError,
    AudioFileTooLargeError,
    DailyUploadLimitError,
    LessonNotFoundError,
    LessonOwnerOnlyError,
    NotFoundException,
    NotLessonContactError,
    TranscriptionInProgressError,
    UnsupportedAudioFormatError,
    ValidationException,
)
from src.crud import Store
from src.models import Lesson
from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus
from src.schemas.lessons import (
    ContactSchema,
    LessonSchema,
    ModelOptionSchema,
    ParticipantSchema,
    TranscriptSchema,
)
from src.services.transcription.catalog import default_model, get_options
from src.tasks.transcribe_lesson import transcribe_lesson_task

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".webm", ".mp4"}
UPLOAD_CHUNK_BYTES = 1024 * 1024


class LessonService:
    """Уроки: загрузка записи, запуск транскрибации, чтение результата.

    Урок видят автор и участники, с которыми он поделился; менять урок и видеть
    служебные данные (ошибка, повтор, участники) может только автор.
    Правила: docs/TRANSCRIPTION.md, раздел 11.
    """

    def __init__(
        self,
        store: Store = Depends(get_store),
    ):
        self._store = store

    @staticmethod
    def get_model_options() -> list[ModelOptionSchema]:
        """Варианты транскрибации, из которых пользователь выбирает при загрузке."""
        return [
            ModelOptionSchema(
                id=option.id, title=option.title, description=option.description
            )
            for option in get_options()
        ]

    async def create_lesson(
        self,
        teacher_id: int,
        title: str,
        file: UploadFile,
        topic: str | None = None,
        model: TranscriptionModel | None = None,
    ) -> LessonSchema:
        """Сохраняет аудио, создаёт урок с транскриптом PENDING и ставит задачу.

        model — вариант транскрибации; если не указан, берётся вариант по умолчанию.
        """
        extension = Path(file.filename or "").suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedAudioFormatError

        lesson_id = uuid4()
        daily_left = await self._daily_upload_left(teacher_id)
        audio_path, size = await self._save_audio(
            file, lesson_id, extension, daily_left
        )
        try:
            await self._store.lesson.add(
                return_model=False,
                id=lesson_id,
                teacher_id=teacher_id,
                title=title,
                topic=(topic or "").strip() or None,
                transcription_model=model or default_model(),
                audio_path=str(audio_path),
                audio_size_bytes=size,
            )
            transcript = await self._store.lesson_transcript.add(
                lesson_id=lesson_id, status=TranscriptStatus.PENDING
            )
            # Коммитим до постановки задачи: иначе воркер может не увидеть строки.
            await self._store.session.commit()
        except Exception:
            audio_path.unlink(missing_ok=True)
            raise

        transcribe_lesson_task.delay(str(transcript.id))
        lesson = await self._store.lesson.find_by_id(model_id=lesson_id)
        return self._to_schema(lesson, transcript.status)

    async def retry_transcription(
        self,
        teacher_id: int,
        lesson_id: UUID,
        model: TranscriptionModel | None = None,
    ) -> LessonSchema:
        """Запускает транскрибацию урока заново (после сбоя или другим вариантом).

        Прежний результат стирается. model меняет вариант транскрибации урока;
        без него используется тот, что выбран у урока.
        """
        lesson = await self._get_owned_lesson(teacher_id, lesson_id)
        transcript = await self._store.lesson_transcript.find_one_or_none(
            lesson_id=lesson_id
        )
        if transcript is None:
            raise NotFoundException("Транскрипт урока не найден")
        # Параллельный второй запуск того же файла только впустую грузил бы процессор.
        if transcript.status == TranscriptStatus.PROCESSING:
            raise TranscriptionInProgressError
        if not lesson.audio_path or not Path(lesson.audio_path).is_file():
            raise AudioFileMissingError

        if model is not None and model != lesson.transcription_model:
            await self._store.lesson.update(
                model_id=lesson_id, return_model=False, transcription_model=model
            )
        await self._store.lesson_transcript.update(
            model_id=transcript.id,
            return_model=False,
            status=TranscriptStatus.PENDING,
            language=None,
            segments=None,
            error=None,
            note=None,
        )
        # Коммитим до постановки задачи: иначе воркер может увидеть старое состояние.
        await self._store.session.commit()

        transcribe_lesson_task.delay(str(transcript.id))
        lesson = await self._store.lesson.find_by_id(model_id=lesson_id)
        return self._to_schema(lesson, TranscriptStatus.PENDING)

    async def list_lessons(
        self, user_id: int, limit: int, offset: int, shared: bool = False
    ) -> list[LessonSchema]:
        """Свои уроки или, при shared=True, уроки, которыми поделились с пользователем."""
        if shared:
            rows = await self._store.lesson.find_shared_with(
                user_id=user_id, limit=limit, offset=offset
            )
        else:
            rows = await self._store.lesson.find_by_teacher(
                teacher_id=user_id, limit=limit, offset=offset
            )
        return [
            self._to_schema(lesson, status, is_owner=not shared)
            for lesson, status in rows
        ]

    async def get_lesson(self, user_id: int, lesson_id: UUID) -> LessonSchema:
        lesson, is_owner = await self._get_visible_lesson(user_id, lesson_id)
        transcript = await self._store.lesson_transcript.find_one_or_none(
            lesson_id=lesson_id
        )
        return self._to_schema(
            lesson, transcript.status if transcript else None, is_owner=is_owner
        )

    async def get_transcript(self, user_id: int, lesson_id: UUID) -> TranscriptSchema:
        _, is_owner = await self._get_visible_lesson(user_id, lesson_id)
        transcript = await self._store.lesson_transcript.find_one_or_none(
            lesson_id=lesson_id
        )
        if transcript is None:
            raise NotFoundException("Транскрипт урока не найден")
        result = TranscriptSchema.model_validate(transcript)
        if is_owner:
            return result
        # Участник видит только готовый текст, без ошибок и промежуточных статусов.
        if result.status != TranscriptStatus.DONE:
            return result.model_copy(
                update={
                    "status": TranscriptStatus.PENDING,
                    "language": None,
                    "segments": [],
                    "error": None,
                    "note": None,
                }
            )
        return result.model_copy(update={"error": None})

    async def list_contacts(self, user_id: int) -> list[ContactSchema]:
        """С кем пользователь может поделиться уроком."""
        rows = await self._store.lesson_participant.find_contacts(user_id=user_id)
        return [ContactSchema(**row) for row in rows]

    async def list_participants(
        self, owner_id: int, lesson_id: UUID
    ) -> list[ParticipantSchema]:
        await self._get_owned_lesson(owner_id, lesson_id)
        rows = await self._store.lesson_participant.find_for_lesson(lesson_id=lesson_id)
        return [ParticipantSchema(**row) for row in rows]

    async def add_participant(
        self, owner_id: int, lesson_id: UUID, user_id: int
    ) -> list[ParticipantSchema]:
        """Делится уроком; повторное добавление того же участника ничего не меняет."""
        await self._get_owned_lesson(owner_id, lesson_id)
        if user_id == owner_id:
            raise ValidationException("Нельзя поделиться записью с самим собой")
        if not await self._store.lesson_participant.is_contact(owner_id, user_id):
            raise NotLessonContactError
        if not await self._store.lesson_participant.is_participant(lesson_id, user_id):
            await self._store.lesson_participant.add(
                return_model=False, lesson_id=lesson_id, user_id=user_id
            )
        return await self.list_participants(owner_id, lesson_id)

    async def remove_participant(
        self, requester_id: int, lesson_id: UUID, user_id: int
    ) -> None:
        """Автор убирает любого участника, участник может убрать только себя."""
        lesson, is_owner = await self._get_visible_lesson(requester_id, lesson_id)
        if not is_owner and requester_id != user_id:
            raise LessonOwnerOnlyError
        await self._store.lesson_participant.remove(
            lesson_id=lesson.id, user_id=user_id
        )

    async def _get_visible_lesson(
        self, user_id: int, lesson_id: UUID
    ) -> tuple[Lesson, bool]:
        """Урок для автора или участника; второе значение - является ли он автором."""
        lesson = await self._store.lesson.find_by_id(model_id=lesson_id)
        if lesson is not None:
            if lesson.teacher_id == user_id:
                return lesson, True
            if await self._store.lesson_participant.is_participant(lesson_id, user_id):
                return lesson, False
        # Чужой урок отдаём как несуществующий, чтобы не раскрывать его наличие.
        raise LessonNotFoundError

    async def _get_owned_lesson(self, teacher_id: int, lesson_id: UUID) -> Lesson:
        lesson, is_owner = await self._get_visible_lesson(teacher_id, lesson_id)
        if not is_owner:
            raise LessonOwnerOnlyError
        return lesson

    @staticmethod
    def _to_schema(
        lesson: Lesson, status: TranscriptStatus | None, is_owner: bool = True
    ) -> LessonSchema:
        # Участнику не показываем ход распознавания и сбои: только готово или ещё нет.
        if not is_owner and status is not None and status != TranscriptStatus.DONE:
            status = TranscriptStatus.PENDING
        return LessonSchema(
            id=lesson.id,
            title=lesson.title,
            topic=lesson.topic,
            transcription_model=lesson.transcription_model,
            created_at=lesson.created_at,
            transcript_status=status,
            is_owner=is_owner,
        )

    async def _daily_upload_left(self, teacher_id: int) -> "DailyQuota":
        """Сколько байт пользователь ещё может загрузить за текущие сутки."""
        limit = settings.LESSON_DAILY_UPLOAD_MB * 1024 * 1024
        now = datetime.now(timezone.utc)
        used, oldest = await self._store.lesson.uploaded_since(
            teacher_id=teacher_id, since=now - DAILY_WINDOW
        )
        quota = DailyQuota(left=limit - used, oldest_upload=oldest, now=now)
        if quota.left <= 0:
            raise quota.error()
        return quota

    @staticmethod
    async def _save_audio(
        file: UploadFile, lesson_id: UUID, extension: str, daily: "DailyQuota"
    ) -> tuple[Path, int]:
        """Пишет загрузку на диск кусками, не читая весь файл в память.

        Возвращает путь и размер файла. Останавливается, как только файл превысил
        предел на одну загрузку или остаток суточного лимита.
        """
        directory = Path(settings.LESSON_AUDIO_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{lesson_id}{extension}"
        file_limit = settings.MAX_LESSON_UPLOAD_MB * 1024 * 1024

        written = 0
        try:
            with path.open("wb") as out:
                while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                    written += len(chunk)
                    if written > file_limit:
                        raise AudioFileTooLargeError
                    if written > daily.left:
                        raise daily.error()
                    await asyncio.to_thread(out.write, chunk)
            if written == 0:
                raise ValidationException("Файл пустой")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path, written


DAILY_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class DailyQuota:
    """Остаток суточного лимита загрузки и данные для понятного отказа."""

    left: int
    oldest_upload: datetime | None
    now: datetime

    def error(self) -> DailyUploadLimitError:
        limit_mb = settings.LESSON_DAILY_UPLOAD_MB
        message = f"Суточный лимит загрузки ({limit_mb} МБ за 24 часа) исчерпан."
        if self.oldest_upload is not None:
            oldest = self.oldest_upload
            # SQLite отдаёт время без пояса; в базе оно хранится в UTC.
            if oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            wait = max(oldest + DAILY_WINDOW - self.now, timedelta(minutes=1))
            hours, minutes = divmod(int(wait.total_seconds()) // 60, 60)
            message += f" Лимит начнёт освобождаться через {hours} ч {minutes} мин."
        return DailyUploadLimitError(message)
