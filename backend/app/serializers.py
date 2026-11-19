import json

from app.models import Order, Product


def product_images(p: Product) -> list[str]:
    """详情图集：images JSON 数组优先；旧数据只有 image 时兜底为 [image]"""
    if p.images:
        try:
            arr = json.loads(p.images)
            if isinstance(arr, list) and arr:
                return [str(u) for u in arr]
        except (ValueError, TypeError):
            pass
    return [p.image] if p.image else []


def product_to_dict(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "brand": p.brand, "spec": p.spec,
        "unit": p.unit, "origin": p.origin,
        "price_original": p.price_original, "price_sale": p.price_sale,
        "image": p.image, "images": product_images(p),
        "category_id": p.category_id, "status": p.status,
        "stock": p.stock, "sort": p.sort,
    }


STATUS_LABEL = {"PENDING": "待备货", "READY": "待取货", "DONE": "已完成", "CANCELLED": "已取消"}


def order_to_dict(o: Order, include_user: bool = False) -> dict:
    d = {
        "id": o.id, "order_no": o.order_no, "status": o.status,
        "status_label": STATUS_LABEL[o.status], "total": o.total,
        "remark": o.remark, "pickup_code": o.pickup_code,
        "pickup_date": o.pickup_date.isoformat() if o.pickup_date else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "ready_at": o.ready_at.isoformat() if o.ready_at else None,
        "done_at": o.done_at.isoformat() if o.done_at else None,
        "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
        "cancel_reason": o.cancel_reason,
        "items": [{
            "p_name": i.p_name, "p_spec": i.p_spec, "p_unit": i.p_unit,
            "p_price": i.p_price, "qty": i.qty, "subtotal": i.subtotal,
        } for i in o.items],
    }
    if include_user and o.user:
        d["user"] = {"empid": o.user.empid, "name": o.user.name}
    return d

