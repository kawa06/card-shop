from fastapi import HTTPException

from config import settings


def email_configured() -> bool:
    return bool(settings.RESEND_API_KEY)


def twilio_configured() -> bool:
    return bool(
        (settings.TWILIO_ACCOUNT_SID or "").strip()
        and (settings.TWILIO_AUTH_TOKEN or "").strip()
        and (settings.TWILIO_VERIFY_SERVICE_SID or "").strip()
    )


def normalize_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("0"):
        return "+81" + cleaned[1:]
    return cleaned


def send_phone_otp(phone: str) -> dict:
    if not twilio_configured():
        if settings.DEBUG:
            print(f"--- [TWILIO MOCK] OTP SENT TO {phone} ---")
            return {"message": "認証コードを送信しました (DEBUG MODE)", "debug": True}
        raise HTTPException(
            status_code=503,
            detail="SMS認証の設定が完了していません。管理者にお問い合わせください。",
        )

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        verification = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verifications.create(to=phone, channel="sms")
        )
        return {"message": "認証コードを送信しました", "status": verification.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMS送信に失敗しました: {str(e)}")


def verify_phone_code(phone: str, code: str) -> bool:
    if not twilio_configured():
        if settings.DEBUG:
            return code == "000000"
        raise HTTPException(
            status_code=503,
            detail="SMS認証の設定が完了していません。管理者にお問い合わせください。",
        )

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        verification_check = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verification_checks.create(to=phone, code=code)
        )
        return verification_check.status == "approved"
    except Exception as e:
        error_text = str(e).lower()
        if "invalid" in error_text or "not found" in error_text or "expired" in error_text:
            return False
        raise HTTPException(status_code=500, detail=f"認証に失敗しました: {str(e)}")
