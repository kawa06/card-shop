import httpx
from config import settings
import logging

logger = logging.getLogger(__name__)


async def send_verification_email(email: str, token: str) -> tuple[bool, str | None]:
    verification_url = f"{settings.FRONTEND_URL}/verify/{token}"

    if not settings.RESEND_API_KEY:
        if settings.DEBUG:
            logger.info("Verification email mock completed")
            return True, None
        logger.error("RESEND_API_KEY is not configured")
        return False, "RESEND_API_KEY is not configured"

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

    from_address = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_address,
                    "to": [email],
                    "subject": "【KRX TCG】メールアドレス認証のお願い",
                    "html": html_content,
                },
                timeout=30.0,
            )

            if response.status_code in (200, 201):
                logger.info(f"Email sent successfully to {email}")
                return True, None

            error_body = response.text
            logger.error(f"Resend API Error: {response.status_code} - {error_body}")
            return False, f"Resend error ({response.status_code}): {error_body}"
    except Exception as e:
        logger.error(f"Error sending email via Resend: {str(e)}")
        return False, str(e)
