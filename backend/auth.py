from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from admin_emails import ensure_admin
import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ─── Password helpers ───────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT helpers ─────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        return user_id
    except JWTError:
        return None


# ─── Dependencies ─────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_token(token)
    if user_id is None:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return ensure_admin(user, db)


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    if not token:
        return None
    user_id = decode_token(token)
    if user_id is None:
        return None
    return db.query(models.User).filter(models.User.id == int(user_id)).first()


def get_current_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理者権限が必要です",
        )
    return current_user
