from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from admin_emails import ensure_admin
from clerk_auth import authenticate_clerk_session
from internal_admin_auth import authenticate_internal_admin
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
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (JWTError, TypeError, ValueError):
        return None


# ─── Dependencies ─────────────────────────────────────────────────

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )

    internal_user = authenticate_internal_admin(request, db)
    if internal_user is not None:
        return internal_user

    if not token:
        raise credentials_exception

    user_id = decode_token(token)
    if user_id is not None:
        user = db.query(models.User).filter(models.User.id == int(user_id)).first()
        if user is not None:
            return ensure_admin(user, db)

    clerk_user = authenticate_clerk_session(token, db)
    if clerk_user is not None:
        return clerk_user

    raise credentials_exception


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    if not token:
        return None
    user_id = decode_token(token)
    if user_id is not None:
        return db.query(models.User).filter(models.User.id == int(user_id)).first()
    return authenticate_clerk_session(token, db)


def get_current_admin(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.User:
    from services.admin_auth import AdminAccessError, resolve_admin_context

    try:
        resolve_admin_context(db, current_user, request=request, log_failure=True)
    except AdminAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return current_user


def get_current_admin_context(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from services.admin_auth import AdminAccessError, resolve_admin_context

    try:
        return resolve_admin_context(db, current_user, request=request, log_failure=True)
    except AdminAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
