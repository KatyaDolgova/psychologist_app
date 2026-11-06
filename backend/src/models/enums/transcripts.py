import enum


class TranscriptStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class TranscriptionModel(enum.Enum):
    """Вариант транскрибации, который выбирает пользователь.

    Это не имя модели, а готовый вариант: какая именно модель за ним стоит,
    задаётся в настройках (см. services/transcription/catalog.py).
    """

    FAST = "fast"
    QUALITY = "quality"
