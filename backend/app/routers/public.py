from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_settings import get_notice

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/notice")
def notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}
