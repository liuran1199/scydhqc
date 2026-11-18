from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models import Order, OrderItem, Product, User
from app.services.pickup_code import generate_pickup_code


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
                  pickup_code=generate_pickup_code(db))
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
