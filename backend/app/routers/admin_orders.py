from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog, Order, User
from app.serializers import order_to_dict
from app.services.orders import cancel_order, mark_ready

router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"],
                   dependencies=[Depends(get_current_admin)])


@router.get("")
def admin_orders(status: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 pickup_date: str | None = None,
                 q: str | None = None, page: int = Query(1, ge=1),
                 db: Session = Depends(get_db)):
    query = db.query(Order)
    if status:  # 支持逗号分隔多状态，如 PENDING,READY（备货批次角标用）
        query = query.filter(Order.status.in_([s.strip() for s in status.split(",") if s.strip()]))
    if pickup_date:
        query = query.filter(Order.pickup_date == date.fromisoformat(pickup_date))
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


@router.get("/receipts")
def receipts(ids: str | None = None, pickup_date: str | None = None,
             db: Session = Depends(get_db)):
    """打印小票数据：按订单 id 列表，或按取货批次（PENDING/READY）整批出。"""
    query = db.query(Order)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()][:500]
        if not id_list:
            raise AppError(400, "订单 id 无效")
        query = query.filter(Order.id.in_(id_list))
    elif pickup_date:
        query = query.filter(Order.pickup_date == date.fromisoformat(pickup_date),
                             Order.status.in_(["PENDING", "READY"]))
    else:
        raise AppError(400, "请指定订单 id 或取货日期")
    orders = query.order_by(Order.id).limit(500).all()
    return {"items": [order_to_dict(o, include_user=True) for o in orders]}


@router.get("/picking-list")
def picking_list(pickup_date: str | None = None,
                 db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    """备货清单（A4 打印页数据）：按商品汇总 + 按订单明细。
    不传日期默认今晚要备的批次：明天取货的订单（今天 16:00 截单）。"""
    batch = date.fromisoformat(pickup_date) if pickup_date else date.today() + timedelta(days=1)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="export",
                    target="picking-list", detail=f"打印备货清单（{batch:%Y-%m-%d} 取货批次）"))
    db.commit()
    orders = (db.query(Order)
              .filter(Order.status.in_((["PENDING", "READY"])), Order.pickup_date == batch)
              .order_by(Order.id).all())
    agg: dict[tuple, int] = {}
    for o in orders:
        for it in o.items:
            k = (it.p_name, it.p_spec, it.p_unit)
            agg[k] = agg.get(k, 0) + it.qty
    summary = [{"p_name": n, "p_spec": s, "p_unit": u, "qty": q}
               for (n, s, u), q in sorted(agg.items())]
    return {"batch": batch.isoformat(),
            "total_orders": len(orders),
            "total_kinds": len(summary),
            "total_qty": sum(r["qty"] for r in summary),
            "summary": summary,
            "orders": [order_to_dict(o, include_user=True) for o in orders]}
