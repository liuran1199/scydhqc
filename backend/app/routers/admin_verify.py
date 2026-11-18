import re
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog, Order
from app.serializers import STATUS_LABEL, order_to_dict

router = APIRouter(prefix="/api/admin/verify", tags=["verify"],
                   dependencies=[Depends(get_current_admin)])

QR_RE = re.compile(r"^SC:[0-9-]+:(\d{6})$")


def parse_code(raw: str) -> str:
    m = QR_RE.match(raw.strip())
    return m.group(1) if m else raw.strip()


def _find(db: Session, raw: str) -> Order:
    code = parse_code(raw)
    o = db.query(Order).filter_by(pickup_code=code).first()
    if not o:
        raise AppError(404, f"取货码 {code} 不存在，请核对")
    return o


@router.get("/{raw}")
def lookup(raw: str, db: Session = Depends(get_db)):
    o = _find(db, raw)
    d = order_to_dict(o, include_user=True)
    d["verifiable"] = o.status == "READY"
    return {"order": d}


@router.post("/{raw}")
def verify(raw: str, db: Session = Depends(get_db),
           admin: Admin = Depends(get_current_admin)):
    o = _find(db, raw)
    res = db.execute(
        update(Order)
        .where(Order.id == o.id, Order.status == "READY")
        .values(status="DONE", done_at=datetime.now(), verified_by=admin.id)
    )
    if res.rowcount == 0:
        db.rollback()
        current = db.get(Order, o.id).status
        hint = "，请先做备货完成" if current == "PENDING" else ""
        raise AppError(409, f"订单状态为「{STATUS_LABEL[current]}」，不能核销{hint}")
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="verify",
                    target=o.order_no, detail=f"取货码 {o.pickup_code}"))
    db.commit()
    return order_to_dict(db.get(Order, o.id), include_user=True)
