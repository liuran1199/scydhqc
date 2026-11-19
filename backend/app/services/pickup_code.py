import secrets

from sqlalchemy.orm import Session

from app.models import Order


def generate_pickup_code(db: Session) -> str:
    for _ in range(50):  # 全局唯一（含历史），碰撞重试
        code = f"{secrets.randbelow(1000000):06d}"
        if not db.query(Order).filter_by(pickup_code=code).first():
            return code
    raise RuntimeError("取货码生成失败")
