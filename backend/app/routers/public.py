from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_settings import get_notice
from app.services.orders import PICKUP_CUTOFF_HOUR

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/notice")
def notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}


@router.get("/pickup-info")
def pickup_info():
    """确认页取货规则提示。不给具体日期：取货以订单状态（备货完成）为准，
    休息日顺延由取货须知人话说明，系统不做日历承诺。"""
    return {"cutoff_hour": PICKUP_CUTOFF_HOUR}
