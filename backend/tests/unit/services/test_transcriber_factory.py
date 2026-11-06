import pytest

from src.config import settings
from src.models.enums.transcripts import TranscriptionModel
from src.services.transcription import factory, whisper


class FakeTranscriber:
    created: list[str] = []

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        FakeTranscriber.created.append(model_name)


@pytest.fixture(autouse=True)
def fake_engine(monkeypatch):
    """Настоящая модель не грузится: подменяем движок и сбрасываем кэш фабрики."""
    FakeTranscriber.created = []
    monkeypatch.setattr(whisper, "FasterWhisperTranscriber", FakeTranscriber)
    monkeypatch.setattr(factory, "_loaded", None)
    monkeypatch.setattr(settings, "TRANSCRIBER_BACKEND", "faster-whisper")
    monkeypatch.setattr(settings, "WHISPER_MODEL_FAST", "small")
    monkeypatch.setattr(settings, "WHISPER_MODEL_QUALITY", "large-v3-turbo")


def test_variants_map_to_models_from_settings():
    assert factory.get_transcriber(TranscriptionModel.FAST).model_name == "small"
    assert (
        factory.get_transcriber(TranscriptionModel.QUALITY).model_name
        == "large-v3-turbo"
    )


def test_models_follow_settings(monkeypatch):
    monkeypatch.setattr(settings, "WHISPER_MODEL_QUALITY", "large-v3")

    transcriber = factory.get_transcriber(TranscriptionModel.QUALITY)

    assert transcriber.model_name == "large-v3"


def test_same_variant_is_loaded_once():
    first = factory.get_transcriber(TranscriptionModel.QUALITY)
    second = factory.get_transcriber(TranscriptionModel.QUALITY)

    assert first is second
    assert FakeTranscriber.created == ["large-v3-turbo"]


def test_switching_variant_reloads_and_keeps_only_one_model():
    factory.get_transcriber(TranscriptionModel.FAST)
    factory.get_transcriber(TranscriptionModel.QUALITY)
    factory.get_transcriber(TranscriptionModel.QUALITY)

    assert FakeTranscriber.created == ["small", "large-v3-turbo"]
    assert factory._loaded[1] == "large-v3-turbo"


def test_same_model_name_for_both_variants_is_not_reloaded(monkeypatch):
    monkeypatch.setattr(settings, "WHISPER_MODEL_FAST", "small")
    monkeypatch.setattr(settings, "WHISPER_MODEL_QUALITY", "small")

    factory.get_transcriber(TranscriptionModel.FAST)
    factory.get_transcriber(TranscriptionModel.QUALITY)

    assert FakeTranscriber.created == ["small"]


def test_unknown_backend_fails_clearly(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBER_BACKEND", "magic")

    with pytest.raises(ValueError, match="magic"):
        factory.get_transcriber(TranscriptionModel.FAST)
