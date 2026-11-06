import asyncio
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, UploadFile

from src.config import settings
from src.core.dependencies import get_store
from src.core.exceptions import (
    AudioFileMissingError,
    AudioFileTooLargeError,
    LessonNotFoundError,
    NotFoundException,
    TranscriptionInProgressError,
    UnsupportedAudioFormatError,
    ValidationException,
)
from src.crud import Store
from src.models import Lesson
from src.models.enums.transcripts import TranscriptionModel, TranscriptStatus
from src.schemas.lessons import LessonSchema, ModelOptionSchema, TranscriptSchema
from src.services.transcription.catalog import default_model, get_options
from src.tasks.transcribe_lesson import transcribe_lesson_task

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac", ".webm", ".mp4"}
UPLOAD_CHUNK_BYTES = 1024 * 1024


class LessonService:
    """Уроки: загрузка записи, запуск транскрибации, чтение результата.

    Уроки и транскрипты видит только автор урока.
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
        audio_path = await self._save_audio(file, lesson_id, extension)
        try:
            await self._store.lesson.add(
                return_model=False,
                id=lesson_id,
                teacher_id=teacher_id,
                title=title,
                topic=(topic or "").strip() or None,
                transcription_model=model or default_model(),
                audio_path=str(audio_path),
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

    async def get_lesson(self, teacher_id: int, lesson_id: UUID) -> LessonSchema:
        lesson = await self._get_owned_lesson(teacher_id, lesson_id)
        transcript = await self._store.lesson_transcript.find_one_or_none(
            lesson_id=lesson_id
        )
        return self._to_schema(lesson, transcript.status if transcript else None)

    async def get_transcript(
        self, teacher_id: int, lesson_id: UUID
    ) -> TranscriptSchema:
        await self._get_owned_lesson(teacher_id, lesson_id)
        transcript = await self._store.lesson_transcript.find_one_or_none(
            lesson_id=lesson_id
        )
        if transcript is None:
            raise NotFoundException("Транскрипт урока не найден")
        return TranscriptSchema.model_validate(transcript)

    async def _get_owned_lesson(self, teacher_id: int, lesson_id: UUID) -> Lesson:
        lesson = await self._store.lesson.find_by_id(model_id=lesson_id)
        # Чужой урок отдаём как несуществующий, чтобы не раскрывать его наличие.
        if lesson is None or lesson.teacher_id != teacher_id:
            raise LessonNotFoundError
        return lesson

    @staticmethod
    def _to_schema(lesson: Lesson, status: TranscriptStatus | None) -> LessonSchema:
        return LessonSchema(
            id=lesson.id,
            title=lesson.title,
            topic=lesson.topic,
            transcription_model=lesson.transcription_model,
            created_at=lesson.created_at,
            transcript_status=status,
        )

    @staticmethod
    async def _save_audio(file: UploadFile, lesson_id: UUID, extension: str) -> Path:
        """Пишет загрузку на диск кусками, не читая весь файл в память."""
        directory = Path(settings.LESSON_AUDIO_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{lesson_id}{extension}"
        limit = settings.MAX_LESSON_UPLOAD_MB * 1024 * 1024

        written = 0
        try:
            with path.open("wb") as out:
                while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                    written += len(chunk)
                    if written > limit:
                        raise AudioFileTooLargeError
                    await asyncio.to_thread(out.write, chunk)
            if written == 0:
                raise ValidationException("Файл пустой")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path
