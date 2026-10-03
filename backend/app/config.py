"""Configuración central de la app. Lee todo desde variables de entorno / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str = "dev-secret-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 días
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "sqlite:///./centinela.db"

    MP_ACCESS_TOKEN: str = ""
    MP_PLAN_PRICE_ARS: float = 30000
    MP_WEBHOOK_URL: str = "http://localhost:8000/api/subscription/webhook"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    MODELS_DIR: str = "app/models_data"
    FACES_DIR: str = "app/known_faces"
    SNAPSHOTS_DIR: str = "app/snapshots"

    FRONTEND_ORIGIN: str = "http://localhost:5173"


settings = Settings()
