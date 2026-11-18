from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog, Order, User
from app.serializers import STATUS_LABEL, order_to_dict
from app.services.orders import cancel_order, mark_ready

router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"],
                   dependencies=[Depends(get_current_admin)])


@router.get("")
def admin_orders(status: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 q: str | None = None, page: int = Query(1, ge=1),
                 db: Session = Depends(get_db)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if date_from:
        query = query.filter(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Order.created_at
                             < datetime.fromisoformat(date_to) + timedelta(days=1))
    if q:
        like = f"%{q}%"
        query = (query.join(User, Order.user_id == User.id)
                 .filter(or_(Order.order_no.like(like), Order.pickup_code.like(like),
                             User.empid.like(like), User.name.like(like))))
    total = query.count()
    rows = (query.order_by(Order.id.desc()).offset((page - 1) * 20).limit(20).all())
    return {"items": [order_to_dict(o, include_user=True) for o in rows],
            "total": total, "page": page}


class ReadyIn(BaseModel):
    ids: list[int]


@router.post("/ready")
def batch_ready(body: ReadyIn, db: Session = Depends(get_db)):
    updated, failed = 0, []
    for oid in body.ids:
        o = db.get(Order, oid)
        if not o:
            failed.append({"id": oid, "detail": "订单不存在"})
            continue
        try:
            mark_ready(db, o)
            updated += 1
        except AppError as e:
            failed.append({"id": oid, "detail": e.msg})
    return {"updated": updated, "failed": failed}


class CancelIn(BaseModel):
    reason: str


@router.post("/{oid}/cancel")
def admin_cancel(oid: int, body: CancelIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    o = db.get(Order, oid)
    if not o:
        raise AppError(404, "订单不存在")
    cancel_order(db, o, f"管理员取消：{body.reason}", by_admin=True)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="cancel",
                    target=o.order_no, detail=body.reason))
    db.commit()
    return {"ok": True}


@router.get("/picking-list.xlsx")
def picking_list(db: Session = Depends(get_db)):
    orders = (db.query(Order)
              .filter(Order.status.in_(["PENDING", "READY"]))
              .order_by(Order.id).all())
    wb = Workbook()
    ws = wb.active
    ws.title = "按商品汇总"
    ws.append(["商品名称", "规格", "单位", "合计数量"])
    agg: dict[tuple, int] = {}
    for o in orders:
        for it in o.items:
            k = (it.p_name, it.p_spec, it.p_unit)
            agg[k] = agg.get(k, 0) + it.qty
    for (n, s, u), qty in sorted(agg.items()):
        ws.append([n, s, u, qty])
    ws2 = wb.create_sheet("按订单明细")
    ws2.append(["订单号", "状态", "工号", "姓名", "商品", "数量", "总额(元)", "备注", "下单时间"])
    for o in orders:
        items_text = "；".join(f"{i.p_name}×{i.qty}" for i in o.items)
        ws2.append([o.order_no, STATUS_LABEL[o.status], o.user.empid, o.user.name or "",
                    items_text, sum(i.qty for i in o.items), o.total / 100,
                    o.remark, o.created_at.strftime("%m-%d %H:%M")])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=picking-list.xlsx"})
