from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.cas import CASClient, HttpCASClient
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, user_codec
from app.exceptions import AppError
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_cas_client() -> CASClient:
    return HttpCASClient(settings.cas_base_url)


def _callback_url() -> str:
    return f"{settings.app_base_url}/api/auth/cas/callback"


def _upsert_user(db: Session, empid: str, name: str | None) -> User:
    u = db.query(User).filter_by(empid=empid).first()
    if not u:
        u = User(empid=empid, name=name)
        db.add(u)
    else:
        u.last_login_at = datetime.now()
        if name and not u.name:
            u.name = name
    db.commit()
    return u


@router.get("/cas/login")
def cas_login():
    if not settings.cas_base_url:
        raise AppError(500, "未配置 CAS_BASE_URL")
    return RedirectResponse(f"{settings.cas_base_url}/login?service={_callback_url()}",
                            status_code=302)


@router.get("/cas/callback")
def cas_callback(ticket: str, request: Request, db: Session = Depends(get_db),
                 cas: CASClient = Depends(get_cas_client)):
    try:
        empid, name = cas.get_user(ticket, _callback_url())
    except Exception:
        return RedirectResponse("/api/auth/cas/login", status_code=302)  # 静默重试，不甩错误给老师
    user = _upsert_user(db, empid, name)
    resp = RedirectResponse("/m/", status_code=302)
    resp.set_cookie("sc_session", user_codec.dumps({"uid": user.id}),
                    httponly=True, samesite="lax")
    return resp


@router.get("/dev-login")
def dev_login(empid: str, name: str | None = None, db: Session = Depends(get_db)):
    if not settings.dev_auth_enabled:
        raise AppError(403, "开发登录未启用")
    user = _upsert_user(db, empid, name)
    resp = JSONResponse({"empid": user.empid, "name": user.name})
    resp.set_cookie("sc_session", user_codec.dumps({"uid": user.id}),
                    httponly=True, samesite="lax")
    return resp


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"empid": user.empid, "name": user.name, "phone": user.phone}


class ProfileIn(BaseModel):
    name: str | None = None
    phone: str | None = None


@router.put("/me")
def update_me(body: ProfileIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name
    if body.phone:
        user.phone = body.phone
    db.commit()
    return {"empid": user.empid, "name": user.name, "phone": user.phone}
