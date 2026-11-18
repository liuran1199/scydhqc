import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # 必须在 import app 之前
os.environ.setdefault("DEV_AUTH_ENABLED", "1")  # 测试依赖 dev-login 旁路

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.ratelimit import order_limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """模块级内存限流器跨测试隔离（否则同进程内命中数互相污染）。"""
    order_limiter.hits.clear()
    yield
    order_limiter.hits.clear()


@pytest.fixture()
def db():
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    settings.dev_auth_enabled = True
    with TestClient(app) as c:
        yield c
