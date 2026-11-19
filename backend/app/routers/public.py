from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_settings import get_notice
from app.services.orders import PICKUP_CUTOFF_HOUR, pickup_date_for
from app.utils.times import now_cst

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/notice")
def notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}


@router.get("/pickup-info")
def pickup_info():
    """服务端按业务时区（Asia/Shanghai）算下一批取货日期。
    前端确认页以此为准，不再依赖老师手机的设备时间。"""
    now = now_cst()
    return {"pickup_date": pickup_date_for(now).isoformat(),
            "cutoff_hour": PICKUP_CUTOFF_HOUR}
