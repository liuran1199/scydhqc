from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Admin, AdminLog, Order

router = APIRouter(prefix="/api/admin/stats", tags=["stats"],
                   dependencies=[Depends(get_current_admin)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    now = datetime.now()
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow0 = today0 + timedelta(days=1)
    done_today = (db.query(Order)
                  .filter(Order.status == "DONE", Order.done_at >= today0,
                          Order.done_at < tomorrow0).all())
    last7 = []
    for i in range(6, -1, -1):
        d0 = today0 - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        orders = db.query(Order).filter(Order.created_at >= d0,
                                        Order.created_at < d1).count()
        sales = sum(o.total for o in db.query(Order)
                    .filter(Order.status == "DONE", Order.done_at >= d0,
                            Order.done_at < d1).all())
        last7.append({"date": d0.strftime("%m-%d"), "orders": orders,
                      "sales": sales})
    return {
        "today_new": db.query(Order).filter(Order.created_at >= today0,
                                            Order.created_at < tomorrow0).count(),
        "pending": db.query(Order).filter_by(status="PENDING").count(),
        "ready": db.query(Order).filter_by(status="READY").count(),
        "today_done_count": len(done_today),
        "today_done_amount": sum(o.total for o in done_today),
        "last7": last7,
    }


def _range_done(db: Session, date_from: str, date_to: str):
    d0 = datetime.fromisoformat(date_from)
    d1 = datetime.fromisoformat(date_to) + timedelta(days=1)
    return (d0, d1,
            db.query(Order).filter(Order.status == "DONE", Order.done_at >= d0,
                                   Order.done_at < d1).all())


@router.get("")
def range_stats(date_from: str, date_to: str, db: Session = Depends(get_db)):
    d0, d1, done = _range_done(db, date_from, date_to)
    by_status = {"PENDING": 0, "READY": 0, "DONE": 0, "CANCELLED": 0}
    for o in db.query(Order).filter(Order.created_at >= d0, Order.created_at < d1).all():
        by_status[o.status] = by_status.get(o.status, 0) + 1
    agg: dict[str, dict] = {}
    for o in done:
        for it in o.items:
            a = agg.setdefault(it.p_name, {"name": it.p_name, "qty": 0, "amount": 0})
            a["qty"] += it.qty
            a["amount"] += it.subtotal
    top = sorted(agg.values(), key=lambda x: -x["qty"])[:10]
    return {"order_count": sum(by_status.values()), "done_count": len(done),
            "done_amount": sum(o.total for o in done), "by_status": by_status,
            "top_products": top}


@router.get("/export")
def export(date_from: str, date_to: str, db: Session = Depends(get_db),
           admin: Admin = Depends(get_current_admin)):
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="export",
                    target="reconciliation", detail=f"导出核销流水 {date_from}~{date_to}"))
    db.commit()
    _, _, done = _range_done(db, date_from, date_to)
    wb = Workbook()
    ws = wb.active
    ws.title = "核销流水"
    ws.append(["取货时间", "订单号", "取货码", "工号", "姓名",
               "商品明细", "总额(元)", "核销人"])
    admins = {a.id: a.username for a in db.query(Admin).all()}
    for o in sorted(done, key=lambda x: x.done_at):
        ws.append([o.done_at.strftime("%Y-%m-%d %H:%M"), o.order_no, o.pickup_code,
                   o.user.empid, o.user.name or "",
                   "；".join(f"{i.p_name}×{i.qty}" for i in o.items),
                   o.total / 100, admins.get(o.verified_by, "")])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reconciliation.xlsx"})
