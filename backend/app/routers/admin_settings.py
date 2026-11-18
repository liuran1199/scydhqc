from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, require_super
from app.exceptions import AppError
from app.models import Admin, AdminLog, Setting
from app.utils.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin-settings"])


@router.get("/admins", dependencies=[Depends(require_super)])
def list_admins(db: Session = Depends(get_db)):
    rows = db.query(Admin).order_by(Admin.id).all()
    return [{"id": a.id, "username": a.username, "role": a.role, "name": a.name,
             "is_active": a.is_active, "last_login_at":
             a.last_login_at.isoformat() if a.last_login_at else None}
            for a in rows]


class AdminIn(BaseModel):
    username: str
    password: str
    role: str = "operator"
    name: str = ""


@router.post("/admins", dependencies=[Depends(require_super)])
def create_admin(body: AdminIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    if body.role not in ("super", "operator"):
        raise AppError(400, "角色不合法")
    if len(body.password) < 6:
        raise AppError(400, "密码至少 6 位")
    if db.query(Admin).filter_by(username=body.username).first():
        raise AppError(400, "用户名已存在")
    a = Admin(username=body.username, password_hash=hash_password(body.password),
              role=body.role, name=body.name)
    db.add(a)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="admin_create",
                    target=body.username))
    db.commit()
    return {"id": a.id, "username": a.username, "role": a.role}


class AdminUpdateIn(BaseModel):
    password: str | None = None
    role: str | None = None
    name: str | None = None
    is_active: bool | None = None


@router.put("/admins/{aid}", dependencies=[Depends(require_super)])
def update_admin(aid: int, body: AdminUpdateIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    a = db.get(Admin, aid)
    if not a:
        raise AppError(404, "账号不存在")
    if body.password:
        a.password_hash = hash_password(body.password)
        a.failed_attempts, a.locked_until = 0, None
    if body.role:
        a.role = body.role
    if body.name is not None:
        a.name = body.name
    if body.is_active is not None:
        a.is_active = body.is_active
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="admin_update",
                    target=a.username, detail=str(body.model_dump(exclude={"password"}))))
    db.commit()
    return {"ok": True}


@router.get("/logs", dependencies=[Depends(require_super)])
def list_logs(page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    q = db.query(AdminLog)
    total = q.count()
    rows = q.order_by(AdminLog.id.desc()).offset((page - 1) * 20).limit(20).all()
    return {"items": [{"id": l.id, "username": l.username, "action": l.action,
                       "target": l.target, "detail": l.detail,
                       "created_at": l.created_at.isoformat()} for l in rows],
            "total": total, "page": page}


class NoticeIn(BaseModel):
    content: str


def get_notice(db: Session) -> str:
    s = db.get(Setting, "notice_content")
    return s.value if s else ""


@router.get("/settings/notice", dependencies=[Depends(require_super)])
def read_notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}


@router.put("/settings/notice", dependencies=[Depends(require_super)])
def write_notice(body: NoticeIn, db: Session = Depends(get_db)):
    s = db.get(Setting, "notice_content")
    if not s:
        s = Setting(key="notice_content")
        db.add(s)
    s.value = body.content
    db.commit()
    return {"ok": True}
