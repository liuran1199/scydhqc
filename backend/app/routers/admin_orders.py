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
from app.services.orders import (PICKUP_CUTOFF_HOUR, cancel_order, complete_order,
                                 mark_ready, prep_cutoff)

router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"],
                   dependencies=[Depends(get_current_admin)])

# 打印接口单次上限：超了必须明确报错，不能静默截断漏单
PRINT_LIMIT = 500


def parse_date(s: str, name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise AppError(400, f"{name} 格式不正确，应为 YYYY-MM-DD")


def parse_datetime(s: str, name: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise AppError(400, f"{name} 格式不正确")


@router.get("")
def admin_orders(status: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 pickup_date: str | None = None, queue: int = Query(0, ge=0, le=1),
                 q: str | None = None, page: int = Query(1, ge=1),
                 db: Session = Depends(get_db)):
    query = db.query(Order)
    if queue:  # 待备队列：PENDING 且下单 ≤ 截点（与备货单/小票同口径）
        query = query.filter(Order.status == "PENDING",
                             Order.created_at <= prep_cutoff())
    elif status:  # 支持逗号分隔多状态，如 PENDING,READY
        query = query.filter(Order.status.in_([s.strip() for s in status.split(",") if s.strip()]))
    if pickup_date:
        query = query.filter(Order.pickup_date == parse_date(pickup_date, "取货日期"))
    if date_from:
        query = query.filter(Order.created_at >= parse_datetime(date_from, "起始日期"))
    if date_to:
        query = query.filter(Order.created_at
                             < parse_datetime(date_to, "截止日期") + timedelta(days=1))
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
def batch_ready(body: ReadyIn, db: Session = Depends(get_db),
                admin: Admin = Depends(get_current_admin)):
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
    if updated:
        db.add(AdminLog(admin_id=admin.id, username=admin.username, action="ready",
                        target="batch", detail=f"批量备货完成 {updated} 单"))
        db.commit()
    return {"updated": updated, "failed": failed}


class CancelIn(BaseModel):
    reason: str


@router.get("/by-code/{code}")
def order_by_code(code: str, db: Session = Depends(get_db)):
    """窗口核销：按取货码查单（老师出示 6 位码或扫码均走这里）。"""
    o = db.query(Order).filter(Order.pickup_code == code.strip()).first()
    if not o:
        raise AppError(404, "取货码不存在，请核对")
    return order_to_dict(o, include_user=True)


class CompleteIn(BaseModel):
    code: str


@router.post("/complete")
def complete(body: CompleteIn, db: Session = Depends(get_db),
             admin: Admin = Depends(get_current_admin)):
    """窗口核销取货：按取货码标记完成（货已交付），核销人与日志在服务内同事务落库。"""
    o = db.query(Order).filter(Order.pickup_code == body.code.strip()).first()
    if not o:
        raise AppError(404, "取货码不存在，请核对")
    o = complete_order(db, o, admin)
    return order_to_dict(o, include_user=True)


@router.post("/{oid}/cancel")
def admin_cancel(oid: int, body: CancelIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    o = db.get(Order, oid)
    if not o:
        raise AppError(404, "订单不存在")
    cancel_order(db, o, f"管理员取消：{body.reason}", by_admin=True, admin=admin)
    return {"ok": True}


@router.get("/receipts")
def receipts(ids: str | None = None, db: Session = Depends(get_db)):
    """打印小票数据：按订单 id 列表，或不传参 = 当前待备队列（与备货单同口径）。"""
    query = db.query(Order)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if not id_list:
            raise AppError(400, "订单 id 无效")
        if len(id_list) > PRINT_LIMIT:
            raise AppError(400, f"一次最多打印 {PRINT_LIMIT} 单，请分批")
        query = query.filter(Order.id.in_(id_list))
    else:
        query = query.filter(Order.status == "PENDING",
                             Order.created_at <= prep_cutoff())
    total = query.count()
    if total > PRINT_LIMIT:
        raise AppError(400, f"本批 {total} 单超过单次打印上限 {PRINT_LIMIT}，请分批处理")
    orders = query.order_by(Order.id).limit(PRINT_LIMIT).all()
    return {"items": [order_to_dict(o, include_user=True) for o in orders]}


@router.get("/picking-list")
def picking_list(db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    """备货清单（A4 打印页数据）：当前待备队列，按商品汇总 + 按订单明细。

    队列制：PENDING 且下单时间 ≤ 截点（16 点前=全部未备，16 点后=当日 16 点前）。
    不依赖取货日期——周末/节假日没人处理就持续积压，开工一打开全在这里。
    """
    cutoff = prep_cutoff()
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="export",
                    target="picking-list", detail=f"打印备货清单（截至 {cutoff:%m-%d %H:%M} 待备队列）"))
    db.commit()
    orders = (db.query(Order)
              .filter(Order.status == "PENDING", Order.created_at <= cutoff)
              .order_by(Order.id).all())
    agg: dict[tuple, int] = {}
    for o in orders:
        for it in o.items:
            k = (it.p_name, it.p_spec, it.p_unit)
            agg[k] = agg.get(k, 0) + it.qty
    summary = [{"p_name": n, "p_spec": s, "p_unit": u, "qty": q}
               for (n, s, u), q in sorted(agg.items())]
    return {"cutoff": cutoff.isoformat(),
            "cutoff_hour": PICKUP_CUTOFF_HOUR,
            "total_orders": len(orders),
            "total_kinds": len(summary),
            "total_qty": sum(r["qty"] for r in summary),
            "summary": summary,
            "orders": [order_to_dict(o, include_user=True) for o in orders]}
