from pydantic_settings import BaseSettings
from pydantic import field_validator
import secrets
import os
from typing import Optional, List


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
        "https://frontend-one-topaz-20.vercel.app",
        "https://oripa-kawa.vercel.app",
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

    # Email Settings (to be set in Railway environment variables)
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: str = "noreply@oripa-kawa.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "Oripa_kawa"
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False
    USE_CREDENTIALS: bool = True

    # Frontend URL for verification links
    FRONTEND_URL: str = "https://frontend-one-topaz-20.vercel.app"


settings = Settings()
