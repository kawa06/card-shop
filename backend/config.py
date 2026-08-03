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
    def normalize_email_env_aliases(self):
        """Railway may use EMAIL_FROM / EMAIL_FROM_NAME instead of MAIL_*."""
        email_from = os.environ.get("EMAIL_FROM", "").strip()
        if email_from and self.MAIL_FROM == "oripakawa@gmail.com":
            self.MAIL_FROM = email_from
        email_from_name = os.environ.get("EMAIL_FROM_NAME", "").strip()
        if email_from_name and self.MAIL_FROM_NAME == "KRX TCG":
            self.MAIL_FROM_NAME = email_from_name
        email_reply = os.environ.get("EMAIL_REPLY_TO", "").strip()
        if email_reply and self.MAIL_REPLY_TO == "oripakawa@gmail.com":
            self.MAIL_REPLY_TO = email_reply
        username = (self.MAIL_USERNAME or "").strip()
        if username.endswith("@gmail.com"):
            if not self.MAIL_FROM or self.MAIL_FROM.endswith("@oripa-kawa.com"):
                self.MAIL_FROM = username
        elif (self.MAIL_FROM or "").endswith("@gmail.com") and not username:
            self.MAIL_USERNAME = self.MAIL_FROM
        return self

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
        "https://card-vault-public.vercel.app",
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
    MAIL_USERNAME: Optional[str] = "oripakawa@gmail.com"
    MAIL_PASSWORD: Optional[str] = None
    MAIL_FROM: str = "oripakawa@gmail.com"
    MAIL_REPLY_TO: str = "oripakawa@gmail.com"
    MAIL_PORT: int = 465
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "KRX TCG"
    MAIL_TLS: bool = False
    MAIL_SSL: bool = True
    USE_CREDENTIALS: bool = True
    EMAIL_TEMPLATES_ENABLED: bool = True

    # Frontend URL for verification links
    FRONTEND_URL: str = "https://frontend-one-topaz-20.vercel.app"

    # Buylist public site (CORS / email links — optional in Phase 3)
    BUYLIST_URL: str = "https://card-vault-public.vercel.app"

    # Cloudflare R2 (private KYC document storage)
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: Optional[str] = None
    R2_API_TOKEN: Optional[str] = None

    # Payout account field encryption (32+ chars recommended)
    BUYBACK_PAYOUT_ENCRYPTION_KEY: str = ""

    # Guardian consent link validity (days)
    BUYBACK_GUARDIAN_CONSENT_EXPIRE_DAYS: int = 14

    # Buyback label print / ラベル屋さん (optional overrides; defaults in code)
    BUYBACK_SHOP_NAME: str = "KRX TCG"
    BUYBACK_LABEL_PRODUCT_CODE: str = "72265"

    # DeepL API
    DEEPL_API_KEY: str = ""

    # Exchange Rate (USD -> JPY)
    EXCHANGE_RATE_USD_JPY: float = 150.0

    # Bank transfer: payment deadline hours from order creation
    BANK_TRANSFER_PAYMENT_DEADLINE_HOURS: int = 48

    # Optional qualified invoice settings (seed shop_settings on first migrate; DB is source of truth)
    INVOICE_REGISTRATION_NUMBER: str = ""
    INVOICE_ISSUER_NAME: str = ""

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

    @field_validator("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ACCOUNT_ID", "R2_BUCKET_NAME", "R2_API_TOKEN", mode="before")
    @classmethod
    def normalize_r2_secret(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().replace("\n", "").replace("\r", "")
        return v


settings = Settings()
