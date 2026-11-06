from src.config import settings
from src.models.enums.transcripts import TranscriptionModel
from src.services.transcription.base import Transcriber
from src.services.transcription.catalog import get_option

# В памяти держим одну модель: две крупные одновременно займут много ОЗУ.
# Смена варианта между уроками стоит секунды загрузки (модель уже на диске).
_loaded: tuple[str, str, Transcriber] | None = None


def get_transcriber(model: TranscriptionModel) -> Transcriber:
    """Возвращает движок для выбранного варианта; повторно использует загруженный."""
    global _loaded

    backend = settings.TRANSCRIBER_BACKEND
    model_name = get_option(model).whisper_model
    if _loaded is not None and _loaded[:2] == (backend, model_name):
        return _loaded[2]

    # Освобождаем прежнюю модель до загрузки новой.
    _loaded = None
    if backend == "faster-whisper":
        from src.services.transcription.whisper import FasterWhisperTranscriber

        transcriber: Transcriber = FasterWhisperTranscriber(model_name)
    else:
        raise ValueError(f"Неизвестный TRANSCRIBER_BACKEND: {backend}")
    _loaded = (backend, model_name, transcriber)
    return transcriber
