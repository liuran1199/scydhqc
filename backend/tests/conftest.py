import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # 必须在 import app 之前

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app


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
