from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from typing import Optional
import os
from database import get_db
from config import settings
from database import get_db
from admin_emails import normalize_email, is_admin_email, ensure_admin
from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_optional
from mail import send_verification_email
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


class ClerkProvisionRequest(BaseModel):
    email: str
    password: str
    name: str


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
        is_admin=is_admin_email(email),
        verification_token=verification_token,
        phone_number=phone_number,
        phone_verified=phone_verified,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if email_configured() or settings.DEBUG:
        sent, error = await send_verification_email(user.email, verification_token)
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
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )

    user = ensure_admin(user, db)
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/clerk-provision", response_model=AuthResponse)
def clerk_provision(
    payload: ClerkProvisionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Clerk連携用: メール認証なしでユーザーを作成/更新する（サーバー間のみ）"""
    sync_secret = (os.getenv("AUTH_SYNC_SECRET") or "").strip()
    header_secret = (request.headers.get("X-Auth-Sync-Secret") or "").strip()
    if not sync_secret or header_secret != sync_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    email = normalize_email(payload.email)
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()

    if user:
        user.password_hash = hash_password(payload.password)
        if payload.name.strip():
            user.name = payload.name.strip()
        user.is_verified = True
        ensure_admin(user, db)
        db.commit()
        db.refresh(user)
    else:
        user = models.User(
            email=email,
            name=payload.name.strip() or email.split("@")[0],
            password_hash=hash_password(payload.password),
            is_admin=is_admin_email(email),
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ensure_admin(current_user, db)


@router.put("/me", response_model=schemas.UserOut)
def update_profile(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.postal_code is not None:
        current_user.postal_code = payload.postal_code
    if payload.country is not None:
        current_user.country = payload.country
    if payload.region is not None:
        current_user.region = payload.region
    if payload.city is not None:
        current_user.city = payload.city
    if payload.address_line1 is not None:
        current_user.address_line1 = payload.address_line1
    if payload.address_line2 is not None:
        current_user.address_line2 = payload.address_line2
    if payload.address is not None:
        current_user.address = payload.address
    if payload.phone_number is not None:
        current_user.phone_number = payload.phone_number

    db.commit()
    db.refresh(current_user)
    return current_user


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

    sent, error = await send_verification_email(current_user.email, token)
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
