from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.exceptions import AppError
from app.models import Order, User
from app.ratelimit import order_limiter
from app.serializers import order_to_dict
from app.services.orders import cancel_order, create_order

router = APIRouter(prefix="/api/orders", tags=["orders"])


class ItemIn(BaseModel):
    product_id: int
    qty: int
    price_sale: int | None = None  # 加购时的价格快照，用于改价检测


class OrderIn(BaseModel):
    items: list[ItemIn]
    remark: str = ""


@router.post("")
def submit_order(body: OrderIn, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    if not order_limiter.allow(f"uid:{user.id}"):
        raise AppError(429, "下单太频繁，请稍后再试")
    order = create_order(db, user, [i.model_dump() for i in body.items], body.remark)
    return order_to_dict(order)


def _my_order(db: Session, user: User, oid: int) -> Order:
    o = db.get(Order, oid)
    if not o or o.user_id != user.id:
        raise AppError(404, "订单不存在")
    return o


@router.get("")
def my_orders(status: str | None = None, page: int = Query(1, ge=1),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Order).filter(Order.user_id == user.id)
    if status:
        q = q.filter(Order.status == status)
    total = q.count()
    rows = (q.order_by(Order.id.desc()).offset((page - 1) * 20).limit(20).all())
    return {"items": [order_to_dict(o) for o in rows], "total": total, "page": page}


@router.get("/{oid}")
def my_order_detail(oid: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return order_to_dict(_my_order(db, user, oid))


@router.post("/{oid}/cancel")
def my_order_cancel(oid: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    o = _my_order(db, user, oid)
    cancel_order(db, o, "用户取消")
    return {"ok": True}
