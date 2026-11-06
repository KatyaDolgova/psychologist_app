from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    STATIC_BASE_URL: str
    POSTGRES_HOST: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str

    RESEND_API_KEY: str
    RESEND_EMAIL: str

    ACCESS_SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_DAYS: int

    SMS_AERO_LOGIN: str
    SMS_AERO_KEY: str
    SMS_AERO_SIGN: str

    LIVEKIT_WS_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    SLOT_HORIZON_DAYS: int = 60

    # Транскрибация уроков. Значения по умолчанию рассчитаны на CPU без видеокарты;
    # при наличии GPU: WHISPER_MODEL_QUALITY=large-v3, WHISPER_DEVICE=cuda,
    # WHISPER_COMPUTE_TYPE=float16. Пользователь выбирает вариант "fast" или
    # "quality" при загрузке урока, модели за ними задаются здесь.
    TRANSCRIBER_BACKEND: str = "faster-whisper"
    WHISPER_MODEL_FAST: str = "small"
    WHISPER_MODEL_QUALITY: str = "large-v3-turbo"
    # "fast" по умолчанию: "quality" (large-v3-turbo) на одном из тестовых отрывков
    # зациклился на одном слове, пока нет защиты от этого, безопаснее "fast".
    DEFAULT_TRANSCRIPTION_MODEL: str = "fast"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    # Пакетный режим: на CPU в 2-3 раза быстрее при том же качестве (замеры в docs).
    WHISPER_BATCHED: bool = True
    WHISPER_BATCH_SIZE: int = 8
    TRANSCRIBE_LANGUAGE: str | None = "ru"

    # Аудио уроков хранится вне /static: статика раздаётся публично.
    LESSON_AUDIO_DIR: str = "media/lessons"
    MAX_LESSON_UPLOAD_MB: int = 500

    class Config:
        env_file = ".env"
        extra = "allow"

    @property
    def DATABASE_URL(self):
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
