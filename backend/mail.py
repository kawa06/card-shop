import logging

from sqlalchemy.orm import Session

from config import settings
from services.email_delivery import send_templated_email

logger = logging.getLogger(__name__)


async def send_verification_email(db: Session, email: str, token: str) -> tuple[bool, str | None]:
    verification_url = f"{settings.FRONTEND_URL}/verify/{token}"

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

    subject = "【KRX TCG】メールアドレス認証のお願い"
    result = send_templated_email(
        db,
        template_key="member_email_verify",
        to_email=email,
        variables={"email": email, "url": verification_url, "content": "メールアドレスの認証をお願いします。"},
        fallback_subject=subject,
        fallback_html=html_content,
        reference_type="user",
        reference_id=email,
    )
    if result.ok:
        logger.info("Email sent successfully to %s", email)
    return result.ok, result.error
