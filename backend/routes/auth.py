from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from typing import Optional
import os
from database import get_db
from config import settings
from database import get_db
from admin_emails import normalize_email
import schemas_email
from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_optional
from mail import send_verification_email
from services.customer_auth_security import (
    create_login_otp_challenge,
    ensure_not_locked,
    is_user_locked,
    list_login_history,
    record_login_failure,
    record_login_success,
    verify_login_otp,
)
from services.verification import (
    email_configured,
    twilio_configured,
    normalize_phone,
    send_phone_otp as dispatch_phone_otp,
    verify_phone_code,
)
import models
import schemas
import secrets

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: schemas.UserOut
    debug_token: Optional[str] = None

    class Config:
        from_attributes = True


def _auth_response(user: models.User) -> dict:
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


def _maybe_require_2fa(db: Session, user: models.User) -> Optional[dict]:
    ensure_not_locked(user)
    if user.two_factor_enabled:
        challenge_id, _ = create_login_otp_challenge(db, user)
        db.commit()
        return {
            "requires_2fa": True,
            "challenge_id": challenge_id,
            "user_id": user.id,
            "message": "認証コードをメールで送信しました",
        }
    return None


class ClerkProvisionRequest(BaseModel):
    email: str
    password: str
    name: str
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


@router.get("/setup-status", status_code=status.HTTP_200_OK)
def auth_setup_status():
    """Which auth providers are configured (no secrets exposed)."""
    return {
        "debug": settings.DEBUG,
        "email_configured": email_configured(),
        "sms_configured": twilio_configured(),
        "twilio_account_sid_set": bool((settings.TWILIO_ACCOUNT_SID or "").strip()),
        "twilio_auth_token_set": bool((settings.TWILIO_AUTH_TOKEN or "").strip()),
        "twilio_verify_service_sid_set": bool((settings.TWILIO_VERIFY_SERVICE_SID or "").strip()),
        "resend_api_key_set": bool((settings.RESEND_API_KEY or "").strip()),
        "mail_from": settings.MAIL_FROM,
        "frontend_url": settings.FRONTEND_URL,
        "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT_NAME"),
        "railway_project": os.getenv("RAILWAY_PROJECT_NAME"),
        "env_has_twilio_sid": "TWILIO_ACCOUNT_SID" in os.environ,
        "env_has_resend_key": "RESEND_API_KEY" in os.environ,
        "env_has_auth_sync_secret": "AUTH_SYNC_SECRET" in os.environ,
        "env_has_clerk_secret": "CLERK_SECRET_KEY" in os.environ,
        "env_has_clerk_publishable_key": "CLERK_PUBLISHABLE_KEY" in os.environ
        or "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" in os.environ,
    }


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    email = normalize_email(payload.email)
    existing = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="このメールアドレスは既に使用されています")

    phone_number = normalize_phone(payload.phone_number) if payload.phone_number else None
    phone_verified = False

    if phone_number and payload.phone_verification_code:
        if not verify_phone_code(phone_number, payload.phone_verification_code):
            raise HTTPException(status_code=400, detail="電話番号の認証コードが正しくありません")
        phone_verified = True

    verification_token = secrets.token_urlsafe(32)
    user = models.User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        is_admin=False,
        verification_token=verification_token,
        phone_number=phone_number,
        phone_verified=phone_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if email_configured() or settings.DEBUG:
        sent, error = await send_verification_email(db, user.email, verification_token)
        if not sent and not settings.DEBUG:
            db.delete(user)
            db.commit()
            raise HTTPException(
                status_code=502,
                detail=f"認証メールの送信に失敗しました。Resendのドメイン設定を確認してください。 ({error})",
            )
    else:
        db.delete(user)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="メール認証の設定が完了していません。管理者にお問い合わせください。",
        )

    token = create_access_token({"sub": str(user.id)})
    res = {"access_token": token, "token_type": "bearer", "user": user}
    if settings.DEBUG and not email_configured():
        res["debug_token"] = verification_token
    return res


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            ensure_not_locked(user)
            record_login_failure(db, user, request)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )

    ensure_not_locked(user)

    challenge = _maybe_require_2fa(db, user)
    if challenge:
        return JSONResponse(status_code=202, content=challenge)

    record_login_success(db, user, method="legacy", request=request)
    db.commit()
    return _auth_response(user)


@router.post("/clerk-provision")
def clerk_provision(
    payload: ClerkProvisionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Clerk連携用: メール認証なしでユーザーを作成/更新する（サーバー間のみ）"""
    sync_secret = (os.getenv("AUTH_SYNC_SECRET") or "").strip()
    header_secret = (request.headers.get("X-Auth-Sync-Secret") or "").strip()
    if not sync_secret or not secrets.compare_digest(header_secret, sync_secret):
        raise HTTPException(status_code=403, detail="Forbidden")

    email = normalize_email(payload.email)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()

    if user:
        user.password_hash = hash_password(payload.password)
        if payload.name.strip():
            user.name = payload.name.strip()
        user.is_verified = True
        db.commit()
        db.refresh(user)
    else:
        user = models.User(
            email=email,
            name=payload.name.strip() or email.split("@")[0],
            password_hash=hash_password(payload.password),
            is_admin=False,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    challenge = _maybe_require_2fa(db, user)
    if challenge:
        return JSONResponse(status_code=202, content=challenge)

    record_login_success(
        db,
        user,
        method="clerk",
        ip=payload.client_ip,
        user_agent=payload.user_agent,
    )
    db.commit()
    return _auth_response(user)


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return current_user


@router.put("/me", response_model=schemas.UserOut)
def update_profile(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from services.user_profile import update_customer_profile

    return update_customer_profile(
        db,
        user=current_user,
        name=payload.name,
        family_name=payload.family_name,
        given_name=payload.given_name,
        family_name_kana=payload.family_name_kana,
        given_name_kana=payload.given_name_kana,
        birth_date=payload.birth_date,
        postal_code=payload.postal_code,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        phone_number=payload.phone_number,
    )


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: schemas.PasswordChangeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="現在のパスワードが正しくありません",
        )
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return None


@router.post("/request-verification", status_code=status.HTTP_200_OK)
async def request_verification(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_verified:
        return {"message": "既に認証済みです"}

    if not email_configured() and not settings.DEBUG:
        raise HTTPException(
            status_code=503,
            detail="メール認証の設定が完了していません。管理者にお問い合わせください。",
        )

    token = secrets.token_urlsafe(32)
    current_user.verification_token = token
    db.commit()

    sent, error = await send_verification_email(db, current_user.email, token)
    if not sent and not settings.DEBUG:
        raise HTTPException(
            status_code=502,
            detail=f"認証メールの送信に失敗しました。Resendのドメイン設定を確認してください。 ({error})",
        )

    response = {"message": "認証メールを送信しました"}
    if settings.DEBUG and not email_configured():
        response["debug_token"] = token

    return response


@router.get("/verify/{token}", status_code=status.HTTP_200_OK)
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="無効なトークンです")

    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "メール認証が完了しました"}


@router.post("/phone/send", status_code=status.HTTP_200_OK)
async def send_phone_otp(
    payload: schemas.PhoneAuthRequest,
    current_user: Optional[models.User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    phone = normalize_phone(payload.phone)
    return dispatch_phone_otp(phone)


@router.post("/phone/verify", status_code=status.HTTP_200_OK)
async def verify_phone_otp(
    payload: schemas.PhoneVerifyRequest,
    current_user: Optional[models.User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    phone = normalize_phone(payload.phone)

    if not verify_phone_code(phone, payload.code):
        raise HTTPException(status_code=400, detail="認証コードが正しくありません")

    if current_user:
        current_user.phone_number = phone
        current_user.phone_verified = True
        db.commit()

    return {"message": "電話番号の認証が完了しました"}


@router.post("/2fa/verify", response_model=AuthResponse)
def verify_two_factor(
    payload: schemas_email.OtpVerifyIn,
    request: Request,
    db: Session = Depends(get_db),
):
    user = verify_login_otp(
        db,
        challenge_id=payload.challenge_id,
        code=payload.code,
        user_id=payload.user_id,
    )
    record_login_success(db, user, method="legacy", request=request)
    db.commit()
    return _auth_response(user)


@router.get("/2fa/settings", response_model=schemas_email.TwoFactorSettingsOut)
def get_two_factor_settings(
    current_user: models.User = Depends(get_current_user),
):
    return schemas_email.TwoFactorSettingsOut(
        enabled=bool(current_user.two_factor_enabled),
        method=current_user.two_factor_method,
    )


@router.put("/2fa/settings", response_model=schemas_email.TwoFactorSettingsOut)
def update_two_factor_settings(
    payload: schemas_email.TwoFactorToggleIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.two_factor_enabled = bool(payload.enabled)
    current_user.two_factor_method = "email" if payload.enabled else None
    db.commit()
    db.refresh(current_user)
    return schemas_email.TwoFactorSettingsOut(
        enabled=bool(current_user.two_factor_enabled),
        method=current_user.two_factor_method,
    )


@router.get("/login-history", response_model=list[schemas_email.LoginHistoryOut])
def get_login_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_login_history(db, current_user.id, limit=20)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    db.query(models.Order).filter(models.Order.user_id == current_user.id).delete()

    db.delete(current_user)
    db.commit()
    return None
