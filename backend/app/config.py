from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    UNSPLASH_ACCESS_KEY: str | None = None
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CONNECT_TIMEOUT_SECONDS: int = 3
    REDIS_SOCKET_TIMEOUT_SECONDS: int = 5
    RQ_ML_QUEUE_NAME: str = "tripcraft-ml"
    RQ_ML_JOB_TIMEOUT_SECONDS: int = 600
    RQ_ML_RESULT_TTL_SECONDS: int = 3600
    RQ_ML_FAILURE_TTL_SECONDS: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
