from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from typing import Optional
from database import get_db
from config import settings
from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_optional
from mail import send_verification_email
import models
import schemas
import secrets

router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_EMAILS = {"rikukai0609@icloud.com"}


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


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: schemas.UserCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="このメールアドレスは既に使用されています")

    verification_token = secrets.token_urlsafe(32)
    user = models.User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        is_admin=(payload.email in ADMIN_EMAILS),
        verification_token=verification_token,
        phone_number=payload.phone_number,
        phone_verified=False,  # Always require verification via OTP
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # メール送信をバックグラウンドで実行
    background_tasks.add_task(send_verification_email, user.email, verification_token)

    token = create_access_token({"sub": str(user.id)})
    res = {"access_token": token, "token_type": "bearer", "user": user}
    if not settings.RESEND_API_KEY:
        res["debug_token"] = verification_token
    return res


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="メールアドレスまたはパスワードが正しくありません",
        )
    
    # 認証済みチェック (必要に応じて制限)
    # if not user.is_verified:
    #     raise HTTPException(status_code=403, detail="メールアドレスの認証が完了していません")

    # 管理者メールアドレスなら is_admin を自動的に True にする
    if user.email in ADMIN_EMAILS and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


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
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_verified:
        return {"message": "既に認証済みです"}
    
    token = secrets.token_urlsafe(32)
    current_user.verification_token = token
    db.commit()
    
    # 実際にメールを送信
    background_tasks.add_task(send_verification_email, current_user.email, token)
    
    response = {"message": "認証メールを送信しました"}
    if not settings.RESEND_API_KEY:
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
    # Twilio Verify API start
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_VERIFY_SERVICE_SID:
        # Fallback for debug/test
        print(f"--- [TWILIO MOCK] OTP SENT TO {payload.phone} ---")
        return {"message": "認証コードを送信しました (DEBUG MODE)", "debug": True}

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        verification = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
            .verifications \
            .create(to=payload.phone, channel='sms')
        return {"message": "認証コードを送信しました", "status": verification.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMS送信に失敗しました: {str(e)}")


@router.post("/phone/verify", status_code=status.HTTP_200_OK)
async def verify_phone_otp(
    payload: schemas.PhoneVerifyRequest,
    current_user: Optional[models.User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    # Twilio Verify API check
    is_verified = False
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN or not settings.TWILIO_VERIFY_SERVICE_SID:
        # Fallback for debug/test
        if payload.code == "000000":
            is_verified = True
        else:
            raise HTTPException(status_code=400, detail="認証コードが正しくありません (DEBUG: 000000 を入力してください)")
    else:
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            verification_check = client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID) \
                .verification_checks \
                .create(to=payload.phone, code=payload.code)
            
            if verification_check.status == 'approved':
                is_verified = True
            else:
                raise HTTPException(status_code=400, detail="認証コードが正しくありません")
        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=500, detail=f"認証に失敗しました: {str(e)}")

    if is_verified:
        if current_user:
            current_user.phone_number = payload.phone
            current_user.phone_verified = True
            db.commit()
        return {"message": "電話番号の認証が完了しました"}
    
    raise HTTPException(status_code=400, detail="認証に失敗しました")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # カート、注文などの関連データも削除（Cascade設定がない場合）
    db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).delete()
    # 注文は履歴として残すか削除するか検討が必要だが、ここではアカウント削除に伴い削除
    db.query(models.Order).filter(models.Order.user_id == current_user.id).delete()
    
    db.delete(current_user)
    db.commit()
    return None
