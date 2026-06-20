import httpx
from config import settings
import os
import logging

logger = logging.getLogger(__name__)

# 旧 SMTP 設定 (コメントアウト)
# from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
# conf = ConnectionConfig(
#     MAIL_USERNAME=settings.MAIL_USERNAME or "",
#     MAIL_PASSWORD=settings.MAIL_PASSWORD or "",
#     MAIL_FROM=settings.MAIL_FROM,
#     MAIL_PORT=settings.MAIL_PORT,
#     MAIL_SERVER=settings.MAIL_SERVER,
#     MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
#     MAIL_STARTTLS=settings.MAIL_TLS,
#     MAIL_SSL_TLS=settings.MAIL_SSL,
#     USE_CREDENTIALS=settings.USE_CREDENTIALS,
#     VALIDATE_CERTS=True
# )

async def send_verification_email(email: str, token: str):
    verification_url = f"{settings.FRONTEND_URL}/verify/{token}"
    
    # Resend API Key が未設定の場合はログ出力のみ (開発用フォールバック)
    if not settings.RESEND_API_KEY:
        print(f"--- [RESEND MOCK] EMAIL SENT TO {email} ---")
        print(f"Verification link: {verification_url}")
        print(f"Token: {token}")
        print("------------------------------------------")
        return

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
        <h2 style="color: #fbbf24;">KRX TCG</h2>
        <p>会員登録ありがとうございます。以下のボタンをクリックして、メールアドレスの認証を完了してください。</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{verification_url}" style="background-color: #fbbf24; color: #000; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">メールアドレスを認証する</a>
        </div>
        <p style="font-size: 14px; color: #333;">ボタンがクリックできない場合は、以下のURLをブラウザに貼り付けてください：</p>
        <p style="font-size: 12px; color: #666; word-break: break-all;">{verification_url}</p>
        <p style="font-size: 12px; color: #666; margin-top: 20px;">このメールに心当たりがない場合は、破棄してください。</p>
        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">&copy; KRX TCG</p>
    </div>
    """

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{settings.MAIL_FROM_NAME} <onboarding@resend.dev>",
                    "to": [email],
                    "subject": "【KRX TCG】メールアドレス認証のお願い",
                    "html": html_content,
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Resend API Error: {response.status_code} - {response.text}")
                # 失敗してもトークン自体はログに出しておく (救済用)
                print(f"FAILED TO SEND EMAIL. Token for {email}: {token}")
            else:
                logger.info(f"Email sent successfully to {email}")
    except Exception as e:
        logger.error(f"Error sending email via Resend: {str(e)}")
        print(f"EXCEPTION DURING EMAIL SEND. Token for {email}: {token}")

