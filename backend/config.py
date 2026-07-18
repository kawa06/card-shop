from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
import secrets
import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Card Shop API"
    SITE_NAME: str = "KRX TCG"
    DEBUG: bool = False

    # Database (Render provides DATABASE_URL; fallback to SQLite for local dev)
    DATABASE_URL: str = "sqlite:///./card_shop.db"

    # JWT (SECRET_KEY must be set in production — random default invalidates tokens on restart)
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @model_validator(mode="after")
    def ensure_secret_key(self):
        if not self.SECRET_KEY.strip():
            if self.DEBUG:
                self.SECRET_KEY = secrets.token_hex(32)
                logger.warning("SECRET_KEY is not set; using ephemeral dev key")
            else:
                generated = secrets.token_hex(32)
                self.SECRET_KEY = generated
                logger.warning(
                    "SECRET_KEY is not set in production; using ephemeral key. "
                    "Set SECRET_KEY in Railway env vars to keep JWTs valid across restarts."
                )
        return self

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
    RESEND_API_KEY: Optional[str] = None
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: str = "noreply@oripa-kawa.com"
    MAIL_PORT: int = 465
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "KRX TCG"
    MAIL_TLS: bool = False
    MAIL_SSL: bool = True
    USE_CREDENTIALS: bool = True

    # Frontend URL for verification links
    FRONTEND_URL: str = "https://frontend-one-topaz-20.vercel.app"

    # DeepL API
    DEEPL_API_KEY: str = ""

    # Exchange Rate (USD -> JPY)
    EXCHANGE_RATE_USD_JPY: float = 150.0

    # Twilio SMS (Verify API)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_VERIFY_SERVICE_SID: Optional[str] = None

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    @field_validator("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", mode="before")
    @classmethod
    def normalize_stripe_secret(cls, v: object) -> object:
        if isinstance(v, str):
            # Railway copy/paste sometimes inserts line breaks into long secrets.
            return v.strip().replace("\n", "").replace("\r", "").replace(" ", "")
        return v
