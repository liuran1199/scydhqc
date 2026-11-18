from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin, User
from app.session_codec import SessionCodec
from app.config import settings
from app.exceptions import AppError

user_codec = SessionCodec(settings.session_secret, settings.session_max_age)
admin_codec = SessionCodec(settings.session_secret, settings.session_max_age)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("sc_session")
    data = user_codec.loads(token) if token else None
    if not data:
        raise AppError(401, "未登录")
    user = db.get(User, data["uid"])
    if not user:
        raise AppError(401, "未登录")
    return user


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    token = request.cookies.get("sc_admin")
    data = admin_codec.loads(token) if token else None
    if not data:
        raise AppError(401, "未登录")
    admin = db.get(Admin, data["aid"])
    if not admin or not admin.is_active:
        raise AppError(401, "未登录")
    return admin


def require_super(admin: Admin = Depends(get_current_admin)) -> Admin:
    if admin.role != "super":
        raise AppError(403, "需要超级管理员权限")
    return admin
