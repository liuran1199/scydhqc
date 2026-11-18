from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_codec, cookie_secure, get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog
from app.utils.security import verify_password

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

LOCK_MINUTES = 10
MAX_FAILS = 5


def _register_fail(db: Session, aid: int) -> None:
    """失败计数用 SQL 原子自增（并发请求不丢计数）；达阈值锁定并清零。"""
    db.execute(
        update(Admin).where(Admin.id == aid)
        .values(failed_attempts=Admin.failed_attempts + 1)
    )
    db.flush()
    db.expire(db.get(Admin, aid))  # 丢弃 identity map 旧值，下面的读取走数据库
    a = db.get(Admin, aid)
    if a.failed_attempts >= MAX_FAILS and not (
            a.locked_until and a.locked_until > datetime.now()):
        db.execute(
            update(Admin).where(Admin.id == aid)
            .values(locked_until=datetime.now() + timedelta(minutes=LOCK_MINUTES),
                    failed_attempts=0)
        )


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter_by(username=body.username).first()
    now = datetime.now()
    if not admin or not verify_password(body.password, admin.password_hash):
        if admin:
            if not (admin.locked_until and admin.locked_until > now):
                _register_fail(db, admin.id)  # 已锁定不累计，锁过期自零重启
            db.commit()
            db.refresh(admin)
            if admin.locked_until and admin.locked_until > now:
                raise AppError(403, f"失败次数过多，锁定至 {admin.locked_until:%H:%M}，请稍后再试")
        raise AppError(401, "用户名或密码错误")
    if not admin.is_active:
        raise AppError(403, "账号已停用")
    if admin.locked_until and admin.locked_until > now:
        raise AppError(403, f"失败次数过多，锁定至 {admin.locked_until:%H:%M}，请稍后再试")
    admin.failed_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now
    db.add(AdminLog(username=admin.username, action="login", target=admin.username))
    db.commit()
    resp = JSONResponse({"id": admin.id, "username": admin.username,
                         "role": admin.role, "name": admin.name})
    resp.set_cookie("sc_admin", admin_codec.dumps({"aid": admin.id}),
                    httponly=True, samesite="lax", secure=cookie_secure(request))
    return resp


@router.post("/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("sc_admin")
    return resp


@router.get("/me")
def me(admin: Admin = Depends(get_current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role,
            "name": admin.name}


def ensure_initial_admin(db: Session) -> None:
    if db.query(Admin).count() == 0:
        from app.config import settings
        from app.utils.security import hash_password
        db.add(Admin(username=settings.initial_admin_username,
                     password_hash=hash_password(settings.initial_admin_password),
                     role="super", name="超级管理员"))
        db.commit()
