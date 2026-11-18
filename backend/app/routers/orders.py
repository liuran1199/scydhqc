from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.exceptions import AppError
from app.models import User
from app.ratelimit import order_limiter
from app.serializers import order_to_dict
from app.services.orders import create_order

router = APIRouter(prefix="/api/orders", tags=["orders"])


class ItemIn(BaseModel):
    product_id: int
    qty: int


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
