from datetime import date, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models import Order, OrderItem, Product, User
from app.serializers import STATUS_LABEL as STATUS_LABELS
from app.services.pickup_code import generate_pickup_code

# 备货截单点：每天 16:00 前下单次日取货，16:00 后下单隔日取货
PICKUP_CUTOFF_HOUR = 16


def pickup_date_for(placed_at: datetime) -> date:
    """下单时间 → 取货日期（16 点截单规则，边界 16:00 整属后一批）。"""
    cutoff = placed_at.replace(hour=PICKUP_CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    return (placed_at + timedelta(days=1 if placed_at < cutoff else 2)).date()


def create_order(db: Session, user: User, items: list[dict], remark: str = "") -> Order:
    if not items:
        raise AppError(400, "订单不能为空")
    # 逐项校验 + 服务端计价
    checked: list[tuple[Product, int]] = []
    for it in items:
        qty = int(it.get("qty", 0))
        if qty < 1 or qty > 999:
            raise AppError(400, "商品数量不合法")
        p = db.get(Product, it.get("product_id"))
        if not p or p.status != "on":
            raise AppError(400, f"商品已下架或不存在（id={it.get('product_id')}），请返回重新确认")
        expected = it.get("price_sale")
        if expected is not None and expected != p.price_sale:
            raise AppError(409, f"「{p.name}」价格已调整，请重新确认最新价格")
        checked.append((p, qty))
    # 原子扣减有限库存（NULL 无限跳过）
    for p, qty in checked:
        if p.stock is not None:
            res = db.execute(
                update(Product)
                .where(Product.id == p.id, Product.stock >= qty)
                .values(stock=Product.stock - qty)
            )
            if res.rowcount == 0:
                db.rollback()
                raise AppError(400, f"「{p.name}」库存不足，请修改数量")
    order = Order(order_no="TMP", user_id=user.id, status="PENDING",
                  remark=(remark or "")[:255],
                  pickup_code=generate_pickup_code(db),
                  pickup_date=pickup_date_for(datetime.now()))
    db.add(order)
    db.flush()  # 拿 id
    order.order_no = f"{datetime.now():%Y%m%d}-{order.id:06d}"
    order.total = 0
    for p, qty in checked:
        db.add(OrderItem(order_id=order.id, product_id=p.id, p_name=p.name,
                         p_spec=p.spec, p_unit=p.unit, p_price=p.price_sale,
                         qty=qty, subtotal=p.price_sale * qty))
        order.total += p.price_sale * qty
    db.commit()
    db.refresh(order)
    return order


def restore_product_stock(db: Session, product_id: int, qty: int) -> None:
    """取消回补：SQL 原子加法（并发取消不虚增）；无限库存（NULL）跳过。"""
    db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock.isnot(None))
        .values(stock=Product.stock + qty)
    )


def cancel_order(db: Session, order: Order, reason: str, by_admin: bool = False) -> Order:
    # 条件更新：仅 PENDING/READY 可取消，并发安全
    res = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status.in_(["PENDING", "READY"]))
        .values(status="CANCELLED", cancelled_at=datetime.now(),
                cancel_reason=reason[:255])
    )
    if res.rowcount == 0:
        db.rollback()
        current = db.get(Order, order.id).status
        raise AppError(409, f"当前状态为「{STATUS_LABELS[current]}」，不能取消")
    db.flush()
    for it in db.query(OrderItem).filter_by(order_id=order.id).all():
        if it.product_id:
            restore_product_stock(db, it.product_id, it.qty)
    db.commit()
    return db.get(Order, order.id)


def mark_ready(db: Session, order: Order) -> Order:
    res = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == "PENDING")
        .values(status="READY", ready_at=datetime.now())
    )
    if res.rowcount == 0:
        db.rollback()
        current = db.get(Order, order.id).status
        raise AppError(409, f"当前状态为「{STATUS_LABELS[current]}」，不能备货完成")
    db.commit()
    return db.get(Order, order.id)


def complete_order(db: Session, order: Order) -> Order:
    """窗口核销取货：货已交到教职工手上，订单转 DONE。
    允许 PENDING 直转（货给了就完成，窗口不做状态卡点）。"""
    res = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status.in_(["PENDING", "READY"]))
        .values(status="DONE", done_at=datetime.now())
    )
    if res.rowcount == 0:
        db.rollback()
        current = db.get(Order, order.id).status
        raise AppError(409, f"当前状态为「{STATUS_LABELS[current]}」，不能核销")
    db.commit()
    return db.get(Order, order.id)
