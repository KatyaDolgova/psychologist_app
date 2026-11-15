from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from src.core.dependencies import get_any_user_id
from src.models.enums.transcripts import TranscriptionModel
from src.schemas.lessons import (
    AddParticipantRequest,
    ContactSchema,
    LessonSchema,
    ModelOptionSchema,
    ParticipantSchema,
    RetryTranscriptionRequest,
    TranscriptSchema,
)
from src.services.lesson import LessonService

router = APIRouter(tags=["Lessons"])


# Маршруты /models и /contacts объявлены до "/{lesson_id}", иначе их адрес
# разбирался бы как UUID урока.
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


@router.get(
    "/contacts",
    summary="С кем можно поделиться уроком",
    description=(
        "Те, с кем у пользователя было неотменённое занятие: для специалиста ученики, "
        "для ученика преподаватели. Недавние сверху."
    ),
)
async def list_contacts(
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> list[ContactSchema]:
    return await service.list_contacts(user_id=user_id)


@router.get(
    "/",
    summary="Мои уроки и присланные мне",
    description=(
        "scope=own - уроки, загруженные пользователем; scope=shared - уроки, которыми "
        "с ним поделились (is_owner=false). Новые сверху."
    ),
)
async def list_lessons(
    scope: Literal["own", "shared"] = Query("own"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> list[LessonSchema]:
    return await service.list_lessons(
        user_id=user_id, limit=limit, offset=offset, shared=scope == "shared"
    )


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
            "Список - GET /lessons/models. Если не указан, берётся вариант по умолчанию."
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
    return await service.get_lesson(user_id=user_id, lesson_id=lesson_id)


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
    return await service.get_transcript(user_id=user_id, lesson_id=lesson_id)


@router.get(
    "/{lesson_id}/participants",
    summary="С кем автор поделился уроком",
    description="Только для автора; участнику вернёт 403.",
)
async def list_participants(
    lesson_id: UUID,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> list[ParticipantSchema]:
    return await service.list_participants(owner_id=user_id, lesson_id=lesson_id)


@router.post(
    "/{lesson_id}/participants",
    status_code=status.HTTP_201_CREATED,
    summary="Поделиться уроком",
    description=(
        "Только для автора. Поделиться можно с тем, с кем было занятие "
        "(GET /lessons/contacts), иначе 403. Повторное добавление ничего не меняет. "
        "Возвращает обновлённый список участников."
    ),
)
async def add_participant(
    lesson_id: UUID,
    data: AddParticipantRequest,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> list[ParticipantSchema]:
    return await service.add_participant(
        owner_id=user_id, lesson_id=lesson_id, user_id=data.user_id
    )


@router.delete(
    "/{lesson_id}/participants/{participant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Убрать участника",
    description=(
        "Автор убирает любого участника, участник может убрать только себя "
        "(передав свой id). Доступ пропадает сразу."
    ),
)
async def remove_participant(
    lesson_id: UUID,
    participant_id: int,
    user_id: int = Depends(get_any_user_id),
    service: LessonService = Depends(),
) -> None:
    await service.remove_participant(
        requester_id=user_id, lesson_id=lesson_id, user_id=participant_id
    )
