from dataclasses import dataclass

from src.config import settings
from src.models.enums.transcripts import TranscriptionModel


@dataclass(frozen=True)
class ModelOption:
    """Вариант транскрибации для пользователя и имя модели за ним."""

    id: TranscriptionModel
    title: str
    description: str
    whisper_model: str


def get_options() -> list[ModelOption]:
    """Доступные варианты. Модели за ними берутся из настроек, чтобы на сервере
    с видеокартой подставить более крупные без правки кода."""
    return [
        ModelOption(
            id=TranscriptionModel.FAST,
            title="Быстро",
            description=(
                "Самая быстрая обработка. Больше ошибок в терминах и именах, "
                "подходит для черновика."
            ),
            whisper_model=settings.WHISPER_MODEL_FAST,
        ),
        ModelOption(
            id=TranscriptionModel.QUALITY,
            title="Точнее",
            description=(
                "Термины и слова распознаются заметно лучше, но обработка "
                "примерно втрое дольше."
            ),
            whisper_model=settings.WHISPER_MODEL_QUALITY,
        ),
    ]


def get_option(model: TranscriptionModel) -> ModelOption:
    return next(option for option in get_options() if option.id == model)


def default_model() -> TranscriptionModel:
    return TranscriptionModel(settings.DEFAULT_TRANSCRIPTION_MODEL)
