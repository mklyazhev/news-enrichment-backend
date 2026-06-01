from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://news:news@localhost:5432/news"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    http_timeout_seconds: float = 10
    http_max_retries: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


_settings = Settings()

def get_settings() -> Settings:
    return _settings
