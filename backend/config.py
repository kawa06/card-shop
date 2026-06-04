from pydantic_settings import BaseSettings
from pydantic import field_validator
import secrets
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Card Shop API"
    DEBUG: bool = True

    # Database (Render provides DATABASE_URL; fallback to SQLite for local dev)
    DATABASE_URL: str = "sqlite:///./card_shop.db"

    # JWT
    SECRET_KEY: str = secrets.token_hex(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS (allow overriding via env var for production frontends)
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://taupe-marshmallow-224b52.netlify.app",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_postgres_url(cls, v):
        # Render uses postgres:// but SQLAlchemy requires postgresql://
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
