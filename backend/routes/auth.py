from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
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

    class Config:
        from_attributes = True


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
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
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 実際にメールを送信（非同期）
    try:
        await send_verification_email(user.email, verification_token)
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Registration continues even if email fails

    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": user}


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
    if payload.address is not None:
        current_user.address = payload.address
    
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
    
    token = secrets.token_urlsafe(32)
    current_user.verification_token = token
    db.commit()
    
    # 実際にメールを送信
    try:
        await send_verification_email(current_user.email, token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"メールの送信に失敗しました: {e}")
    
    return {"message": "認証メールを送信しました"}


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
