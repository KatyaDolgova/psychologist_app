from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from src.core.dependencies import get_any_user_id
from src.models.enums.transcripts import TranscriptionModel
from src.schemas.lessons import (
    LessonSchema,
    ModelOptionSchema,
    RetryTranscriptionRequest,
    TranscriptSchema,
)
from src.services.lesson import LessonService

router = APIRouter(tags=["Lessons"])


# Маршрут объявлен до "/{lesson_id}", иначе "models" разбирался бы как UUID урока.
@router.get(
    "/models",
    summary="Варианты транскрибации",
    description="Из этих вариантов пользователь выбирает при загрузке урока.",
)
async def get_model_options(
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> list[ModelOptionSchema]:
    return service.get_model_options()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить запись урока",
    description=(
        "Принимает аудио/видео урока (mp3, m4a, aac, wav, ogg, flac, webm, mp4) "
        "и запускает транскрибацию в фоне. Статус смотрите в GET /lessons/{id}."
    ),
)
async def create_lesson(
    title: str = Form(..., min_length=1, max_length=255),
    topic: str | None = Form(
        None,
        max_length=500,
        description="Тема или ключевые слова: помогают верно распознать термины.",
    ),
    model: TranscriptionModel | None = Form(
        None,
        description=(
            "Вариант транскрибации: fast (быстро) или quality (точнее). "
            "Список — GET /lessons/models. Если не указан, берётся вариант по умолчанию."
        ),
    ),
    file: UploadFile = File(...),
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> LessonSchema:
    return await service.create_lesson(
        teacher_id=user_id, title=title, file=file, topic=topic, model=model
    )


@router.get(
    "/{lesson_id}",
    summary="Урок и статус транскрибации",
)
async def get_lesson(
    lesson_id: UUID,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> LessonSchema:
    return await service.get_lesson(teacher_id=user_id, lesson_id=lesson_id)


@router.post(
    "/{lesson_id}/retry",
    summary="Повторить транскрибацию",
    description=(
        "Запускает транскрибацию урока заново: после сбоя или чтобы получить текст другим "
        "вариантом (поле model). Прежний результат стирается. Пока транскрибация "
        "выполняется, вернёт 409."
    ),
)
async def retry_transcription(
    lesson_id: UUID,
    data: RetryTranscriptionRequest | None = None,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> LessonSchema:
    return await service.retry_transcription(
        teacher_id=user_id,
        lesson_id=lesson_id,
        model=data.model if data else None,
    )


@router.get(
    "/{lesson_id}/transcript",
    summary="Транскрипт урока",
    description="Сегменты с таймкодами; пока статус не DONE, сегментов нет.",
)
async def get_transcript(
    lesson_id: UUID,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> TranscriptSchema:
    return await service.get_transcript(teacher_id=user_id, lesson_id=lesson_id)
