from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from config import settings
import os

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME or "",
    MAIL_PASSWORD=settings.MAIL_PASSWORD or "",
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_TLS,
    MAIL_SSL_TLS=settings.MAIL_SSL,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=True
)

async def send_verification_email(email: str, token: str):
    # If credentials are not set, just print for local development
    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        print(f"--- MOCK EMAIL SENT TO {email} ---")
        print(f"Verification link: {settings.FRONTEND_URL}/verify/{token}")
        print("---------------------------------")
        return

    verification_url = f"{settings.FRONTEND_URL}/verify/{token}"
    
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
        <h2 style="color: #fbbf24;">Oripa_kawa へようこそ！</h2>
        <p>会員登録ありがとうございます。以下のボタンをクリックして、メールアドレスの認証を完了してください。</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" style="background-color: #fbbf24; color: #000; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">メールアドレスを認証する</a>
        </div>
        <p style="font-size: 12px; color: #666;">このメールに心当たりがない場合は、破棄してください。</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">&copy; Oripa_kawa</p>
    </div>
    """

    message = MessageSchema(
        subject="【Oripa_kawa】メールアドレス認証のお願い",
        recipients=[email],
        body=html,
        subtype=MessageType.html
    )

    fm = FastMail(conf)
    await fm.send_message(message)
