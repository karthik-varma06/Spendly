from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    frontend_origin: str = "http://localhost:5173"

    # Split models
    openrouter_vision_model: str = "openrouter/free"
    openrouter_chat_model: str = "openrouter/free"
    openrouter_api_key: str = ""

    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"

    upload_dir: str = "uploads"
    tesseract_cmd: str = ""

    app_name: str = "SPENDLY"


@lru_cache
def get_settings() -> Settings:
    return Settings()