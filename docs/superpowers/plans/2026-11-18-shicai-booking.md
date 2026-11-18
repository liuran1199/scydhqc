# 食材服务点线上预订系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为后勤处食材服务点建一套「企微 H5 预订 + PC 管理后台」系统：教职工 CAS 登录浏览下单，后勤处备货、取货码核销、现场收款。

**Architecture:** 单体 FastAPI + MySQL，托管单页 Vue3 应用（/m 教职工端 Vant、/admin 管理端 Element Plus）。线上只做信息流（预订/备货/核销），不动资金流。订单状态机 PENDING→READY→DONE，可取消。

**Tech Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + MySQL 8；Vue3 + Vite + Pinia + Vant + Element Plus；pytest + Playwright；Docker Compose 部署。

**Spec:** `docs/superpowers/specs/2026-11-18-shicai-booking-design.md`（本计划从 spec 出发，执行者需同时读 spec）

## Global Constraints

- 金额一律 **int 分** 存储/传输，前端 `(分/100).toFixed(2)` 显示
- 订单状态只有 `PENDING/READY/DONE/CANCELLED`；仅 PENDING/READY 可取消或核销（数据库条件更新）
- 商品 `stock` 字段 **NULL=无限**；设数值则下单原子扣减（`UPDATE ... WHERE stock>=n`）、取消回补
- 取货码 6 位数字随机、全局唯一（含历史订单）；二维码内容 `SC:{order_no}:{pickup_code}`
- 会话 cookie：教职工 `sc_session`、管理员 `sc_admin`，HttpOnly + SameSite=Lax
- 无限购；教职工端商品仅显示 `status=on`
- 所有 UI 文案中文；提交消息 conventional commits（feat/fix/test/chore/docs）
- 开发基址 `http://10.204.0.146:13000`；配置全部走 `.env`（不入 git）
- 后端测试覆盖率 ≥80%（pytest-cov）
- CAS 对接必须封装为可 mock 的依赖（`get_cas_client`），测试与 E2E 不依赖真 CAS；本地开发用 `DEV_AUTH_ENABLED=1` 的 `/api/auth/dev-login`

## Review Focus

1. **下单瞬间商品已下架/已改价** — 服务端逐项校验并按数据库价重算，拒绝下架品 → Task 7 `test_offshelf_rejected` / `test_price_from_server`
2. **有限库存不足、并发超卖、取消回补** — 原子扣减，不足报错；取消回补 → Task 7 `test_stock_insufficient`、Task 8 `test_cancel_restocks`
3. **重复核销 / 核销非 READY 订单** — 409 + 当前状态中文提示 → Task 12 `test_verify_twice` / `test_verify_pending`
4. **越权访问他人订单（改 URL）** — 404 → Task 8 `test_other_user_order_404`
5. **管理端密码爆破** — 同账号失败 5 次锁 10 分钟 → Task 5 `test_lockout`

---

### Task 1: 后端脚手架（FastAPI + 配置 + 测试基建）

**Files:**
- Create: `backend/requirements.txt`、`backend/app/__init__.py`、`backend/app/config.py`、`backend/app/database.py`、`backend/app/main.py`
- Create: `backend/tests/conftest.py`、`backend/tests/test_health.py`、`backend/.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `app.config.settings`（字段见下）；`app.database.Base/engine/SessionLocal/get_db()`；`create_app() -> FastAPI`；conftest 提供 `client` fixture（TestClient，SQLite 测试库，每用例重建表）

- [ ] **Step 1: 创建虚拟环境与依赖**

```bash
cd /home/lr/scydhqc/backend
python3.11 -m venv .venv && . .venv/bin/activate
```

`backend/requirements.txt`:

```
fastapi>=0.110
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pydantic-settings>=2.2
pymysql>=1.1
cryptography>=42.0
httpx>=0.27
itsdangerous>=2.1
bcrypt>=4.1
openpyxl>=3.1
python-multipart>=0.0.9
pytest>=8.0
pytest-cov>=5.0
```

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: 写失败测试** `backend/tests/test_health.py`

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL（ModuleNotFoundError: app）

- [ ] **Step 4: 实现**

`backend/app/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "食材预订"
    app_base_url: str = "http://10.204.0.146:13000"
    database_url: str = "mysql+pymysql://sc:scpass@127.0.0.1:3306/shicai?charset=utf8mb4"
    session_secret: str = "dev-secret-change-me"
    session_max_age: int = 7 * 24 * 3600
    cas_base_url: str = ""  # 例 https://cas.xxx.edu.cn/cas，联调时填
    dev_auth_enabled: bool = True  # 本地开发登录旁路，上线置 false
    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin123"
    upload_dir: str = "uploads"

    class Config:
        env_file = ".env"


settings = Settings()
```

`backend/app/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base


def create_app() -> FastAPI:
    app = FastAPI(title="食材预订")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
```

`backend/tests/conftest.py`:

```python
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # 必须在 import app 之前

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.config import settings


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
```

注意：`database.py` 引擎在 import 时读环境变量，conftest 里设 `DATABASE_URL` 必须发生在任何 `app.*` import 之前（如上顺序）。

`backend/.env.example`:

```
DATABASE_URL=mysql+pymysql://sc:scpass@127.0.0.1:3306/shicai?charset=utf8mb4
APP_BASE_URL=http://10.204.0.146:13000
SESSION_SECRET=change-me-in-prod
CAS_BASE_URL=
DEV_AUTH_ENABLED=1
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=admin123
```

`.gitignore` 追加（根目录，已有 `.omc/` 一行）：

```
backend/.venv/
backend/.env
backend/test.db
backend/uploads/
__pycache__/
*.pyc
.pytest_cache/
node_modules/
frontend/dist/
```

- [ ] **Step 5: 运行测试通过**

Run: `cd backend && pytest -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend .gitignore
git commit -m "feat: 后端脚手架（FastAPI+配置+测试基建）"
```

---

### Task 2: 数据模型与种子数据（66 SKU）

**Files:**
- Create: `backend/app/models.py`、`backend/seed_data/products_initial.csv`、`backend/seed.py`
- Test: `backend/tests/test_models_seed.py`

**Interfaces:**
- Consumes: `Base`（Task 1）
- Produces: ORM 模型 `User/Admin/Category/Product/Order/OrderItem/AdminLog/Setting`（字段名即接口，后续所有任务使用）；`seed.py: import_products_csv(db, path) -> dict`（返回 {created, updated, categories}）

- [ ] **Step 1: 写失败测试** `backend/tests/test_models_seed.py`

```python
from app.models import Category, Product
from seed import import_products_csv


def test_seed_imports_66_products(db):
    result = import_products_csv(db, "seed_data/products_initial.csv")
    assert result["created"] == 66
    assert db.query(Product).count() == 66
    assert db.query(Category).count() == 5
    p = db.query(Product).filter_by(name="味好美番茄沙司").first()
    assert p.price_original == 780 and p.price_sale == 770  # 分
    assert p.spec == "330g" and p.unit == "袋" and p.status == "on"
    assert p.stock is None  # 无限
    egg = db.query(Product).filter_by(name="柴鸡蛋").first()
    assert egg.price_sale == 13000
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_models_seed.py -v`
Expected: FAIL（No module named app.models）

- [ ] **Step 3: 实现 models.py**

`backend/app/models.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    empid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(20))
    first_login_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default="operator")  # super/operator
    name: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(128), index=True)
    brand: Mapped[str] = mapped_column(String(64), default="")
    spec: Mapped[str] = mapped_column(String(64), default="")   # 规格
    unit: Mapped[str] = mapped_column(String(16), default="件")  # 单位
    origin: Mapped[str] = mapped_column(String(64), default="")  # 产地
    price_original: Mapped[int] = mapped_column(Integer)          # 原价，分
    price_sale: Mapped[int] = mapped_column(Integer)              # 售价，分
    image: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(8), default="on")  # on/off
    stock: Mapped[int | None] = mapped_column(Integer)            # NULL=无限
    sort: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.now)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)  # 分
    remark: Mapped[str] = mapped_column(String(255), default="")
    pickup_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime)
    done_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_reason: Mapped[str] = mapped_column(String(255), default="")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("admins.id"))
    user = relationship("User")
    items = relationship("OrderItem", backref="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    p_name: Mapped[str] = mapped_column(String(128))    # 快照
    p_spec: Mapped[str] = mapped_column(String(64))
    p_unit: Mapped[str] = mapped_column(String(16))
    p_price: Mapped[int] = mapped_column(Integer)        # 快照价，分
    qty: Mapped[int] = mapped_column(Integer)
    subtotal: Mapped[int] = mapped_column(Integer)       # 分


class AdminLog(Base):
    __tablename__ = "admin_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("admins.id"))
    username: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32), index=True)  # login/verify/cancel/price/export/import...
    target: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
```

- [ ] **Step 4: 实现种子数据**

`backend/seed_data/products_initial.csv`（列：分类,名称,规格,单位,品牌,产地,原价元,售价元。价格×100 转分）：

```csv
调味酱料,味好美番茄沙司,330g,袋,,,7.8,7.7
调味酱料,海底捞番茄沙司,320g,袋,,,7.7,7.6
调味酱料,葱伴侣6月香豆瓣酱,800g,瓶,,,14.5,14.2
调味酱料,正张芝麻酱,400g,瓶,,,13.7,13.4
调味酱料,海天黄豆酱,800g,瓶,,,12.1,11.9
调味酱料,海底捞番茄火锅底料,200g,袋,,,14.3,14.0
调味酱料,香满园香油,400ml,瓶,,,19.6,19.2
调味酱料,海天上等蚝油,1kg,瓶,,,13.9,13.6
调味酱料,海天上等蚝油,700g,瓶,,,7.9,7.7
调味酱料,海天零添加味极鲜,750g,瓶,,,20.0,19.6
调味酱料,海天特级一品鲜,500g,瓶,,,10.8,10.6
调味酱料,李锦记醇酿香醋,500g,瓶,,,9.7,9.5
调味酱料,海底捞火锅蘸料,120g,袋,,,5.1,5.0
调味酱料,郫县豆瓣酱,450g,瓶,,,7.1,7.0
调味酱料,百梦多咖喱,100g,盒,,,10.2,10.0
调味酱料,水塔陈醋,420ml,瓶,,,5.0,4.9
调味酱料,花椒油,265ml,瓶,,,14.0,13.7
调味酱料,恒顺香醋,500ml,瓶,,,6.0,5.9
调味酱料,松茸鲜,108g,瓶,,,15.0,14.7
调味酱料,蓝莓酱,340g,瓶,,,18.0,17.6
调味酱料,麻辣香锅,220g,袋,,,15.0,14.7
调味酱料,乌江榨菜,60g,袋,,,2.5,2.5
调味酱料,海天料酒,800ml,瓶,,,5.0,4.9
调味酱料,临沂炒鸡酱,150g,袋,,,10.0,9.8
调味酱料,味精,400g,袋,,,8.0,7.8
香料干调,乡佬汉麻椒,30g,袋,,,6.7,6.5
香料干调,乡佬汉八角大料,50g,袋,,,9.6,9.4
香料干调,乡佬汉桂皮,50g,袋,,,4.8,4.7
香料干调,华畅香叶,10g,袋,,,2.7,2.7
香料干调,乡老汉五香粉,30g,瓶,,,3.0,2.9
香料干调,乡老汉孜然粉,30g,瓶,,,3.0,2.9
香料干调,乡老汉花椒粉,30g,瓶,,,3.0,2.9
香料干调,乡老汉白胡椒粉,30g,瓶,,,2.4,2.4
香料干调,乡老汉干姜粉,40g,瓶,,,3.9,3.8
香料干调,乡老汉烧烤蘸料,30g,袋,,,3.0,2.9
香料干调,黑芝麻,30g,袋,,,2.2,2.2
香料干调,白芝麻,30g,袋,,,2.0,2.0
香料干调,龙口粉丝,300g,袋,,,6.0,5.9
香料干调,椒盐,30g,瓶,,,3.0,2.9
香料干调,朝天椒,50g,袋,,,3.5,3.4
香料干调,银耳,35g,袋,,,4.5,4.4
香料干调,干黄花,80g,袋,,,7.5,7.4
香料干调,乡老汉淀粉,400g,袋,,,3.5,3.4
香料干调,乡老汉生粉,300g,袋,,,4.9,4.8
粮油米面,和粮溢田七色米,2.5kg,袋,,,58.7,57.5
粮油米面,廊雪饺子小麦粉,5kg,袋,,,39.1,38.3
粮油米面,那亩地五常大米,5kg,袋,,,67.5,66.2
粮油米面,金龙鱼豆油,5升,桶,,,56.1,55.0
粮油米面,金珠泉玉米面,2.5kg,袋,,,17.1,16.8
粮油米面,金珠泉玉米渣,2.5kg,袋,,,17.1,16.8
豆类粥料,欣天宏莲子百合粥料,1kg,桶,,,22.4,22.0
豆类粥料,欣天宏紫薯糯米粥料,1kg,桶,,,22.4,22.0
豆类粥料,欣天宏甄选黄豆,900g,桶,,,14.6,14.3
豆类粥料,欣天宏甄选红小豆,1kg,桶,,,29.3,28.7
豆类粥料,欣天宏三色藜麦,1kg,桶,,,48.9,47.9
豆类粥料,欣天宏小米山药南瓜粥料,1kg,桶,,,24.4,23.9
豆类粥料,欣天宏甄选黑米,1kg,桶,,,14.6,14.3
豆类粥料,金珠泉红小豆,2.5kg,袋,,,45.9,45.0
豆类粥料,金珠泉绿豆,2.5kg,袋,,,49.0,48.0
豆类粥料,金珠泉黄豆,2.5kg,袋,,,28.6,28.0
糖蜜蛋品,昊天碧海冰糖,400g,袋,,,5.9,5.8
糖蜜蛋品,昊天碧海沙糖,400g,袋,,,5.9,5.8
糖蜜蛋品,昊天碧海白糖,400g,袋,,,5.9,5.8
糖蜜蛋品,昊天碧海红糖,400g,袋,,,5.9,5.8
糖蜜蛋品,柴鸡蛋,10斤,箱,,,132.6,130.0
糖蜜蛋品,百花蜂蜜,700g,瓶,,,30.6,30.0
```

`backend/seed.py`:

```python
"""初始化数据库：建表 + 导入商品 CSV。用法：python seed.py [--db mysql地址]"""
import csv
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Category, Product


def import_products_csv(db: Session, path: str) -> dict:
    created = updated = 0
    cat_cache: dict[str, Category] = {}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        cat_name = row["分类"].strip()
        if cat_name and cat_name not in cat_cache:
            c = db.query(Category).filter_by(name=cat_name).first()
            if not c:
                c = Category(name=cat_name, sort=len(cat_cache))
                db.add(c)
                db.flush()
            cat_cache[cat_name] = c
        name, spec = row["名称"].strip(), row["规格"].strip()
        p = db.query(Product).filter_by(name=name, spec=spec).first()
        fields = dict(
            category_id=cat_cache[cat_name].id if cat_name else None,
            unit=row["单位"].strip(), brand=row["品牌"].strip(), origin=row["产地"].strip(),
            price_original=int(round(float(row["原价元"]) * 100)),
            price_sale=int(round(float(row["售价元"]) * 100)),
            updated_at=datetime.now(),
        )
        if p:
            for k, v in fields.items():
                setattr(p, k, v)
            updated += 1
        else:
            db.add(Product(name=name, spec=spec, status="on", stock=None, **fields))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "categories": len(cat_cache)}


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--db":
        from sqlalchemy import create_engine
        from app.database import SessionLocal
        engine.dispose()
        engine.conn = create_engine(sys.argv[2])  # 仅提示：正式用法改 DATABASE_URL 环境变量
    Base.metadata.create_all(engine)
    result = import_products_csv(SessionLocal(), "seed_data/products_initial.csv")
    print(result)
```

（`--db` 分支仅是占位提示，实际通过 `DATABASE_URL` 环境变量指定库；执行者可删掉该分支直接用环境变量。）

- [ ] **Step 5: 运行测试通过**

Run: `cd backend && pytest tests/test_models_seed.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: 数据模型与 66 个 SKU 种子数据"
```

---

### Task 3: 前端脚手架（单 SPA 双区 /m + /admin）

**Files:**
- Create: `frontend/package.json`、`frontend/vite.config.ts`、`frontend/index.html`、`frontend/tsconfig.json`
- Create: `frontend/src/main.ts`、`frontend/src/App.vue`、`frontend/src/router/index.ts`、`frontend/src/api/http.ts`、`frontend/src/shared/format.ts`
- Create: `frontend/src/mobile/views/{HomeView,OrdersView,NoticeView}.vue`（占位）、`frontend/src/admin/views/LoginView.vue`（占位）
- Test: `frontend/src/shared/format.test.ts`、`frontend/vitest.config.ts`

**Interfaces:**
- Produces: `api<T>(path, opts?)`（fetch 封装，credentials=include，非 2xx 抛 `ApiError(status, msg)`，msg 取后端 `detail`）；`ApiError` 类；`download(url)`（带 cookie 打开下载）；`fmtMoney(cents): string`；`STATUS_LABEL`；路由表 `/m/*`、`/admin/*`（本任务先注册占位页）

- [ ] **Step 1: 建工程**

`frontend/package.json`:

```json
{
  "name": "shicai-frontend",
  "private": true,
  "version": "0.1.0",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "element-plus": "^2.7.0",
    "pinia": "^2.1.0",
    "qrcode": "^1.5.3",
    "vant": "^4.9.0",
    "vue": "^3.4.0",
    "vue-router": "^4.3.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

`frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: { "/api": "http://127.0.0.1:13000", "/uploads": "http://127.0.0.1:13000" },
  },
  build: { outDir: "dist" },
  test: { environment: "node" },
});
```

`frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>食材预订</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020", "module": "ESNext", "moduleResolution": "bundler",
    "strict": true, "jsx": "preserve", "esModuleInterop": true,
    "skipLibCheck": true, "lib": ["ES2020", "DOM"], "noEmit": true
  },
  "include": ["src"]
}
```

- [ ] **Step 2: 写失败测试** `frontend/src/shared/format.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { fmtMoney } from "./format";

describe("fmtMoney", () => {
  it("分转元保留两位", () => {
    expect(fmtMoney(770)).toBe("7.70");
    expect(fmtMoney(13000)).toBe("130.00");
    expect(fmtMoney(5)).toBe("0.05");
  });
});
```

Run: `cd frontend && npm install && npm test`
Expected: FAIL（fmtMoney 未定义）

- [ ] **Step 3: 实现公共模块**

`frontend/src/shared/format.ts`:

```ts
export function fmtMoney(cents: number): string {
  return (cents / 100).toFixed(2);
}

export const STATUS_LABEL: Record<string, string> = {
  PENDING: "待备货",
  READY: "待取货",
  DONE: "已完成",
  CANCELLED: "已取消",
};
```

`frontend/src/api/http.ts`:

```ts
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    let d: any = {};
    try { d = await res.json(); } catch { /* ignore */ }
    throw new ApiError(res.status, d.detail || `请求失败(${res.status})`);
  }
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? res.json() : res.blob()) as Promise<T>;
}

export function download(url: string) {
  window.open(url, "_blank");
}
```

`frontend/src/main.ts`:

```ts
import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "vant/lib/index.css";
import "element-plus/dist/index.css";

createApp(App).use(createPinia()).use(router).mount("#app");
```

`frontend/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

`frontend/src/router/index.ts`（占位页，后续任务逐个替换）:

```ts
import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/m" },
    { path: "/m", component: () => import("../mobile/views/HomeView.vue") },
    { path: "/m/orders", component: () => import("../mobile/views/OrdersView.vue") },
    { path: "/m/notice", component: () => import("../mobile/views/NoticeView.vue") },
    { path: "/admin/login", component: () => import("../admin/views/LoginView.vue") },
    { path: "/admin", redirect: "/admin/dashboard" },
  ],
});

export default router;
```

三个 mobile 占位视图与 admin 登录占位（每个文件相同结构）：

```vue
<template><div class="p-4">页面建设中</div></template>
```

- [ ] **Step 4: 运行测试与构建**

Run: `cd frontend && npm test && npm run build`
Expected: 测试 1 passed；构建成功产出 dist/

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: 前端脚手架（Vite+Vue3 双区路由+api 封装）"
```

---

### Task 4: 教职工 CAS 认证（含 mock 与 dev 旁路）

**Files:**
- Create: `backend/app/auth/__init__.py`、`backend/app/auth/cas.py`、`backend/app/routers/auth.py`、`backend/app/session_codec.py`、`backend/app/exceptions.py`
- Modify: `backend/app/main.py`（挂路由、注册异常处理器）
- Test: `backend/tests/test_cas_auth.py`

**Interfaces:**
- Consumes: `User` 模型、`settings`
- Produces: `app.deps.get_current_user`（本任务建于 `backend/app/deps.py`，后续所有教职工接口用）；`app.routers.auth.get_cas_client()` 依赖（测试用 `app.dependency_overrides` 覆盖）；`GET /api/auth/cas/login`（302 跳 CAS）、`GET /api/auth/cas/callback?ticket=`（校验后 302 回 /m/ 并种 `sc_session` cookie）、`GET /api/auth/me`、`PUT /api/auth/me {name?, phone?}`、`GET /api/auth/dev-login?empid=&name=`（仅 `dev_auth_enabled`）；`SessionCodec(secret, max_age).dumps(dict)/loads(str)`

- [ ] **Step 1: 写失败测试** `backend/tests/test_cas_auth.py`

```python
from app.auth.cas import FakeCASClient  # 测试用实现


def test_callback_creates_user_and_session(client, db):
    client.app.dependency_overrides[get_cas_client_dep()] = lambda: FakeCASClient(
        {"T001": ("T001", "张老师")}
    )
    r = client.get("/api/auth/cas/callback?ticket=t1", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/m/")
    assert "sc_session" in r.cookies
    me = client.get("/api/auth/me")
    assert me.json()["empid"] == "T001" and me.json()["name"] == "张老师"


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_dev_login_disabled(client):
    from app.config import settings
    settings.dev_auth_enabled = False
    assert client.get("/api/auth/dev-login?empid=T9").status_code == 403
    settings.dev_auth_enabled = True


def test_update_profile_name(client):
    client.get("/api/auth/dev-login?empid=T002")  # 无姓名登录
    assert client.get("/api/auth/me").json()["name"] is None
    r = client.put("/api/auth/me", json={"name": "李老师"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["name"] == "李老师"


def get_cas_client_dep():
    from app.routers.auth import get_cas_client
    return get_cas_client
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_cas_auth.py -v`
Expected: FAIL（import error）

- [ ] **Step 3: 实现**

`backend/app/exceptions.py`:

```python
class AppError(Exception):
    def __init__(self, status: int, msg: str, code: str = "ERROR"):
        self.status, self.msg, self.code = status, msg, code
```

`backend/app/session_codec.py`:

```python
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class SessionCodec:
    def __init__(self, secret: str, max_age: int):
        self.s = URLSafeTimedSerializer(secret)
        self.max_age = max_age

    def dumps(self, data: dict) -> str:
        return self.s.dumps(data)

    def loads(self, token: str) -> dict | None:
        try:
            return self.s.loads(token, max_age=self.max_age)
        except (BadSignature, SignatureExpired):
            return None
```

`backend/app/auth/cas.py`:

```python
import re
import xml.etree.ElementTree as ET

import httpx


class CASClient:  # 接口约定：get_user(ticket, service_url) -> (empid, name|None)
    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        raise NotImplementedError


class HttpCASClient(CASClient):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        r = httpx.post(
            f"{self.base_url}/serviceValidate",
            params={"ticket": ticket, "service": service_url}, timeout=10,
        )
        m = re.search(
            r"<cas:user>(.*?)</cas:user>", r.text, re.S,
        )
        if not m:
            raise RuntimeError("CAS ticket 校验失败")
        empid = m.group(1).strip()
        nm = re.search(
            r'<cas:attribute name="(?:displayName|cn|name|employeeName)"[^>]*>(.*?)</cas:attribute>',
            r.text, re.S,
        )
        name = nm.group(1).strip() if nm else None
        return empid, name
```

在 `backend/tests/conftest.py` 或 `backend/app/auth/cas.py` 底部提供测试实现（放 cas.py，测试与 E2E 复用）：

```python
class FakeCASClient(CASClient):
    """开发/测试用：预先注入 {empid: (empid, name)}，任意 ticket 均通过。"""

    def __init__(self, users: dict[str, tuple[str, str | None]]):
        self.users = users

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        if ticket not in self.users:
            raise RuntimeError("CAS ticket 校验失败")
        return self.users[ticket]
```

`backend/app/deps.py`:

```python
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Admin, User
from app.session_codec import SessionCodec
from app.config import settings
from app.exceptions import AppError

user_codec = SessionCodec(settings.session_secret, settings.session_max_age)
admin_codec = SessionCodec(settings.session_secret, settings.session_max_age)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("sc_session")
    data = user_codec.loads(token) if token else None
    if not data:
        raise AppError(401, "未登录")
    user = db.get(User, data["uid"])
    if not user:
        raise AppError(401, "未登录")
    return user


def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    token = request.cookies.get("sc_admin")
    data = admin_codec.loads(token) if token else None
    if not data:
        raise AppError(401, "未登录")
    admin = db.get(Admin, data["aid"])
    if not admin or not admin.is_active:
        raise AppError(401, "未登录")
    return admin


def require_super(admin: Admin = Depends(get_current_admin)) -> Admin:
    if admin.role != "super":
        raise AppError(403, "需要超级管理员权限")
    return admin
```

`backend/app/routers/auth.py`:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.cas import CASClient, HttpCASClient
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, user_codec
from app.exceptions import AppError
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_cas_client() -> CASClient:
    return HttpCASClient(settings.cas_base_url)


def _callback_url() -> str:
    return f"{settings.app_base_url}/api/auth/cas/callback"


def _upsert_user(db: Session, empid: str, name: str | None) -> User:
    u = db.query(User).filter_by(empid=empid).first()
    if not u:
        u = User(empid=empid, name=name)
        db.add(u)
    else:
        u.last_login_at = datetime.now()
        if name and not u.name:
            u.name = name
    db.commit()
    return u


@router.get("/cas/login")
def cas_login():
    if not settings.cas_base_url:
        raise AppError(500, "未配置 CAS_BASE_URL")
    return RedirectResponse(f"{settings.cas_base_url}/login?service={_callback_url()}")


@router.get("/cas/callback")
def cas_callback(ticket: str, request: Request, db: Session = Depends(get_db),
                 cas: CASClient = Depends(get_cas_client)):
    try:
        empid, name = cas.get_user(ticket, _callback_url())
    except Exception:
        return RedirectResponse("/api/auth/cas/login")  # 静默重试，不甩错误给老师
    user = _upsert_user(db, empid, name)
    resp = RedirectResponse("/m/")
    resp.set_cookie("sc_session", user_codec.dumps({"uid": user.id}),
                    httponly=True, samesite="lax")
    return resp


@router.get("/dev-login")
def dev_login(empid: str, name: str | None = None, db: Session = Depends(get_db)):
    if not settings.dev_auth_enabled:
        raise AppError(403, "开发登录未启用")
    user = _upsert_user(db, empid, name)
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"empid": user.empid, "name": user.name})
    resp.set_cookie("sc_session", user_codec.dumps({"uid": user.id}),
                    httponly=True, samesite="lax")
    return resp


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"empid": user.empid, "name": user.name, "phone": user.phone}


class ProfileIn(BaseModel):
    name: str | None = None
    phone: str | None = None


@router.put("/me")
def update_me(body: ProfileIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name
    if body.phone:
        user.phone = body.phone
    db.commit()
    return {"empid": user.empid, "name": user.name, "phone": user.phone}
```

`backend/app/main.py` 修改（挂路由 + 异常处理）：

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import Base
from app.exceptions import AppError


def create_app() -> FastAPI:
    app = FastAPI(title="食材预订")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse({"detail": exc.msg, "code": exc.code}, status_code=exc.status)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    from app.routers.auth import router as auth_router
    app.include_router(auth_router)
    return app


app = create_app()
```

（`Base` import 保留给后续任务挂 create_all。）

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_cas_auth.py -v`
Expected: 4 passed（FakeCASClient 走 dependency_overrides，真实 httpx 不被调用）

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: CAS 认证与会话（含 mock/dev 旁路）"
```

---

### Task 5: 管理员认证（bcrypt + 锁定 + 角色依赖）

**Files:**
- Create: `backend/app/utils/security.py`、`backend/app/routers/admin_auth.py`
- Modify: `backend/app/main.py`（挂路由、startup 建表+初始超管）、`backend/app/__init__.py` 无需动
- Test: `backend/tests/test_admin_auth.py`

**Interfaces:**
- Consumes: `Admin` 模型、`admin_codec`、`get_current_admin/require_super`（Task 4 deps.py 已建）
- Produces: `hash_password(pw)/verify_password(pw, hash)`；`ensure_initial_admin(db)`（main startup 调用）；`POST /api/admin/auth/login {username,password}`、`POST /api/admin/auth/logout`、`GET /api/admin/auth/me`

- [ ] **Step 1: 写失败测试** `backend/tests/test_admin_auth.py`

```python
from datetime import datetime, timedelta

from app.models import Admin
from app.utils.security import hash_password


def make_admin(db, username="admin", role="super", active=True):
    db.add(Admin(username=username, password_hash=hash_password("pass123"),
                 role=role, name=username, is_active=active))
    db.commit()


def login(client, u="admin", p="pass123"):
    return client.post("/api/admin/auth/login", json={"username": u, "password": p})


def test_login_ok_and_me(client, db):
    make_admin(db)
    r = login(client)
    assert r.status_code == 200 and "sc_admin" in r.cookies
    assert client.get("/api/admin/auth/me").json()["username"] == "admin"


def test_lockout_after_5_failures(client, db):
    make_admin(db)
    for _ in range(5):
        assert login(client, p="wrong").status_code == 401
    assert login(client).status_code == 403  # 第 6 次即使密码对也锁定
    admin = db.query(Admin).first()
    assert admin.locked_until > datetime.now()


def test_lock_expiry_allows_login(client, db):
    make_admin(db)
    for _ in range(5):
        login(client, p="wrong")
    admin = db.query(Admin).first()
    admin.locked_until = datetime.now() - timedelta(seconds=1)
    db.commit()
    assert login(client).status_code == 200


def test_inactive_admin_rejected(client, db):
    make_admin(db, active=False)
    assert login(client).status_code == 403


def test_require_super_blocks_operator(client, db):
    make_admin(db, username="op", role="operator")
    login(client, "op")
    r = client.get("/api/admin/admins")  # Task 14 的超管接口，这里先验证 403 语义
    assert r.status_code in (403, 404)   # 404=接口未建，403=已建且拒绝；本任务后固定 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_admin_auth.py -v`
Expected: FAIL（no module utils.security）

- [ ] **Step 3: 实现**

`backend/app/utils/__init__.py`（空文件）、`backend/app/utils/security.py`:

```python
import bcrypt


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())
```

`backend/app/routers/admin_auth.py`:

```python
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_codec, get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog
from app.utils.security import verify_password

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

LOCK_MINUTES = 10
MAX_FAILS = 5


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter_by(username=body.username).first()
    now = datetime.now()
    if not admin or not verify_password(body.password, admin.password_hash):
        if admin:
            if admin.locked_until and admin.locked_until > now:
                pass
            else:
                admin.failed_attempts += 1
                if admin.failed_attempts >= MAX_FAILS:
                    admin.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                    admin.failed_attempts = 0
        db.commit()
        if admin and admin.locked_until and admin.locked_until > now:
            raise AppError(403, f"失败次数过多，锁定至 {admin.locked_until:%H:%M}，请稍后再试")
        raise AppError(401, "用户名或密码错误")
    if not admin.is_active:
        raise AppError(403, "账号已停用")
    if admin.locked_until and admin.locked_until > now:
        raise AppError(403, f"失败次数过多，锁定至 {admin.locked_until:%H:%M}，请稍后再试")
    admin.failed_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now
    db.add(AdminLog(username=admin.username, action="login", target=admin.username))
    db.commit()
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"id": admin.id, "username": admin.username,
                         "role": admin.role, "name": admin.name})
    resp.set_cookie("sc_admin", admin_codec.dumps({"aid": admin.id}),
                    httponly=True, samesite="lax")
    return resp


@router.post("/logout")
def logout():
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("sc_admin")
    return resp


@router.get("/me")
def me(admin: Admin = Depends(get_current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role,
            "name": admin.name}
```

`ensure_initial_admin`（放在 `backend/app/routers/admin_auth.py` 底部）：

```python
def ensure_initial_admin(db: Session) -> None:
    if db.query(Admin).count() == 0:
        from app.config import settings
        from app.utils.security import hash_password
        db.add(Admin(username=settings.initial_admin_username,
                     password_hash=hash_password(settings.initial_admin_password),
                     role="super", name="超级管理员"))
        db.commit()
```

`backend/app/main.py` 在 `create_app()` 的 `include_router(auth_router)` 后追加：

```python
    from app.routers.admin_auth import router as admin_auth_router, ensure_initial_admin
    app.include_router(admin_auth_router)

    @app.on_event("startup")
    def on_startup():
        from app.database import Base, SessionLocal
        import app.models  # noqa: F401 确保模型注册
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as s:
            ensure_initial_admin(s)
```

并把顶部 import 改为 `from app.database import Base, SessionLocal, engine`。

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_admin_auth.py -v`
Expected: 5 passed（最后一个允许 404/403，Task 14 后收紧为 403）

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 管理员认证（bcrypt+失败锁定+初始超管）"
```

---

### Task 6: 教职工端商品浏览 API

**Files:**
- Create: `backend/app/routers/products.py`、`backend/app/serializers.py`
- Modify: `backend/app/main.py`（挂路由）
- Test: `backend/tests/test_products_api.py`

**Interfaces:**
- Consumes: `get_current_user`、`Product/Category` 模型
- Produces: `GET /api/categories` → `[{id,name}]`（仅启用）；`GET /api/products?category_id=&q=&page=` → `{items:[{id,name,spec,unit,brand,price_sale,price_original,image,category_id}], total, page}`（仅 on，按 sort,id 排序，每页 20）；`GET /api/products/{id}`（off 或不存在 → 404）；`product_to_dict(p)`（serializers.py，管理端复用）

- [ ] **Step 1: 写失败测试** `backend/tests/test_products_api.py`

```python
from app.models import Category, Product


def seed_products(db):
    c = Category(name="调味酱料")
    db.add(c)
    db.flush()
    db.add_all([
        Product(name="海天黄豆酱", spec="800g", unit="瓶", price_original=1210,
                price_sale=1190, category_id=c.id, status="on", sort=1),
        Product(name="乌江榨菜", spec="60g", unit="袋", price_original=250,
                price_sale=250, status="on", sort=2),
        Product(name="下架品", spec="1kg", unit="瓶", price_original=1000,
                price_sale=900, status="off"),
    ])
    db.commit()


def login_teacher(client):
    client.get("/api/auth/dev-login?empid=T001&name=张老师")


def test_list_only_onshelf(client, db):
    seed_products(db)
    login_teacher(client)
    r = client.get("/api/products")
    assert r.status_code == 200
    names = [i["name"] for i in r.json()["items"]]
    assert names == ["海天黄豆酱", "乌江榨菜"]  # 下架品不可见，按 sort 排序


def test_category_filter_and_search(client, db):
    seed_products(db)
    login_teacher(client)
    cid = db.query(Category).first().id
    assert len(client.get(f"/api/products?category_id={cid}").json()["items"]) == 1
    assert client.get("/api/products?q=榨菜").json()["items"][0]["name"] == "乌江榨菜"


def test_detail_offshelf_404(client, db):
    seed_products(db)
    login_teacher(client)
    pid = db.query(Product).filter_by(name="下架品").first().id
    assert client.get(f"/api/products/{pid}").status_code == 404


def test_requires_login(client, db):
    assert client.get("/api/products").status_code == 401
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_products_api.py -v`
Expected: FAIL（路由不存在 → 401/404 断言失败）

- [ ] **Step 3: 实现**

`backend/app/serializers.py`:

```python
from app.models import Product


def product_to_dict(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "brand": p.brand, "spec": p.spec,
        "unit": p.unit, "origin": p.origin,
        "price_original": p.price_original, "price_sale": p.price_sale,
        "image": p.image, "category_id": p.category_id, "status": p.status,
        "stock": p.stock, "sort": p.sort,
    }
```

`backend/app/routers/products.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.exceptions import AppError
from app.models import Category, Product, User
from app.serializers import product_to_dict

router = APIRouter(prefix="/api", tags=["products"], dependencies=[Depends(get_current_user)])


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.query(Category).filter_by(enabled=True).order_by(Category.sort, Category.id).all()
    return [{"id": c.id, "name": c.name} for c in rows]


@router.get("/products")
def list_products(category_id: int | None = None, q: str | None = None,
                  page: int = Query(1, ge=1),
                  db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.status == "on")
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if q:
        query = query.filter(Product.name.contains(q))
    total = query.count()
    rows = (query.order_by(Product.sort, Product.id)
            .offset((page - 1) * 20).limit(20).all())
    return {"items": [product_to_dict(p) for p in rows], "total": total, "page": page}


@router.get("/products/{pid}")
def product_detail(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p or p.status != "on":
        raise AppError(404, "商品不存在或已下架")
    return product_to_dict(p)
```

`backend/app/main.py`：在 auth 路由后追加：

```python
    from app.routers.products import router as products_router
    app.include_router(products_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_products_api.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 教职工商品浏览 API（在售过滤/分类/搜索）"
```

---

### Task 7: 下单服务与 API（服务端计价、快照、原子库存、取货码、限流）

**Files:**
- Create: `backend/app/services/__init__.py`、`backend/app/services/orders.py`、`backend/app/services/pickup_code.py`、`backend/app/ratelimit.py`、`backend/app/routers/orders.py`
- Modify: `backend/app/main.py`（挂路由）
- Test: `backend/tests/test_order_create.py`

**Interfaces:**
- Consumes: `Product/Order/OrderItem/User`、`get_current_user`
- Produces: `create_order(db, user, items: list[dict{product_id,qty}], remark) -> Order`（AppError 400 各业务错误）；`generate_pickup_code(db) -> str`；`RateLimiter(limit, window).allow(key) -> bool`；`POST /api/orders {items:[{product_id,qty}], remark}` → 订单 dict（含取货码，字段见 serializers.order_to_dict）；`order_to_dict(order, include_user=False)`（serializers.py 追加，管理端复用）

- [ ] **Step 1: 写失败测试** `backend/tests/test_order_create.py`

```python
from app.models import Category, Order, OrderItem, Product


def seed(db, stock=None):
    c = Category(name="粮油米面")
    db.add(c)
    db.flush()
    p1 = Product(name="五常大米", spec="5kg", unit="袋", price_original=6750,
                 price_sale=6620, category_id=c.id, status="on", stock=stock)
    p2 = Product(name="豆油", spec="5升", unit="桶", price_original=5610,
                 price_sale=5500, category_id=c.id, status="on")
    db.add_all([p1, p2])
    db.commit()
    return p1, p2


def test_create_order_price_from_server_and_snapshot(client, db):
    p1, p2 = seed(db)
    client.get("/api/auth/dev-login?empid=T001&name=张老师")
    r = client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 2}, {"product_id": p2.id, "qty": 1}],
        "remark": "周五取",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 6620 * 2 + 5500      # 服务端按 DB 价计算
    assert len(d["items"]) == 2
    item = d["items"][0]
    assert item["p_name"] == "五常大米" and item["p_price"] == 6620  # 快照
    assert len(d["pickup_code"]) == 6 and d["pickup_code"].isdigit()
    assert d["order_no"].startswith("20")     # YYYYMMDD-NNNNNN
    assert d["status"] == "PENDING"


def test_offshelf_rejected(client, db):
    p1, _ = seed(db)
    p1.status = "off"
    db.commit()
    client.get("/api/auth/dev-login?empid=T001")
    r = client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    assert r.status_code == 400 and "下架" in r.json()["detail"]


def test_stock_insufficient(client, db):
    p1, _ = seed(db, stock=2)
    client.get("/api/auth/dev-login?empid=T001")
    r = client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 3}]})
    assert r.status_code == 400 and "库存" in r.json()["detail"]
    assert db.query(Order).count() == 0       # 未生成订单


def test_stock_deducted_and_null_unlimited(client, db):
    p1, p2 = seed(db, stock=10)
    client.get("/api/auth/dev-login?empid=T001")
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 3},
                                                {"product_id": p2.id, "qty": 99}]})
    db.expire_all()
    assert db.get(Product, p1.id).stock == 7  # 扣减
    assert db.get(Product, p2.id).stock is None  # NULL 无限不动


def test_invalid_qty_rejected(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    assert client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 0}]}).status_code == 400


def test_rate_limited(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    codes = [client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 1}]}).status_code for _ in range(11)]
    assert codes.count(429) == 1              # 第 11 次 429


def test_pickup_code_unique(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    client.get("/api/auth/dev-login?empid=T002")
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    codes = [o.pickup_code for o in db.query(Order).all()]
    assert len(set(codes)) == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_order_create.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/services/pickup_code.py`:

```python
import random

from sqlalchemy.orm import Session

from app.models import Order


def generate_pickup_code(db: Session) -> str:
    for _ in range(50):  # 全局唯一（含历史），碰撞重试
        code = f"{random.randint(0, 999999):06d}"
        if not db.query(Order).filter_by(pickup_code=code).first():
            return code
    raise RuntimeError("取货码生成失败")
```

`backend/app/services/orders.py`:

```python
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
```

`backend/app/ratelimit.py`:

```python
import time


class RateLimiter:
    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        lst = [t for t in self.hits.get(key, []) if now - t < self.window]
        lst.append(now)
        self.hits[key] = lst
        return len(lst) <= self.limit


order_limiter = RateLimiter(10, 60)  # 每用户每分钟 10 单
```

`backend/app/serializers.py` 追加：

```python
from app.models import Order  # 文件顶部合并 import

STATUS_LABEL = {"PENDING": "待备货", "READY": "待取货", "DONE": "已完成", "CANCELLED": "已取消"}


def order_to_dict(o: Order, include_user: bool = False) -> dict:
    d = {
        "id": o.id, "order_no": o.order_no, "status": o.status,
        "status_label": STATUS_LABEL[o.status], "total": o.total,
        "remark": o.remark, "pickup_code": o.pickup_code,
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
```

`backend/app/routers/orders.py`:

```python
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
```

`backend/app/main.py` 追加挂载：

```python
    from app.routers.orders import router as orders_router
    app.include_router(orders_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_order_create.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 下单 API（服务端计价/快照/原子库存/取货码/限流）"
```

---

### Task 8: 我的订单 API（列表/详情/取消+回补）

**Files:**
- Modify: `backend/app/services/orders.py`（追加 cancel_order）、`backend/app/routers/orders.py`（追加 3 个端点）
- Test: `backend/tests/test_order_cancel.py`

**Interfaces:**
- Consumes: `create_order`
- Produces: `cancel_order(db, order, reason, by_admin=False) -> Order`（条件更新，AppError 409 状态不符）；`GET /api/orders?status=&page=`（仅本人）；`GET /api/orders/{id}`（他人订单 404）；`POST /api/orders/{id}/cancel`（仅本人取消 PENDING/READY）

- [ ] **Step 1: 写失败测试** `backend/tests/test_order_cancel.py`

```python
from datetime import datetime

from app.models import Order, Product
from app.services.orders import create_order


def make_order(client, db, empid="T001", qty=2, stock=None):
    p = Product(name="大米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on", stock=stock)
    db.add(p)
    db.commit()
    client.get(f"/api/auth/dev-login?empid={empid}&name=张老师")
    r = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": qty}]})
    return r.json()


def test_list_and_filter(client, db):
    make_order(client, db)
    r = client.get("/api/orders")
    assert r.json()["total"] == 1
    assert client.get("/api/orders?status=PENDING").json()["total"] == 1
    assert client.get("/api/orders?status=DONE").json()["total"] == 0


def test_other_user_order_404(client, db):
    d = make_order(client, db, empid="T001")
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    assert client.get(f"/api/orders/{d['id']}").status_code == 404
    assert client.post(f"/api/orders/{d['id']}/cancel").status_code == 404


def test_cancel_pending_restocks(client, db):
    d = make_order(client, db, stock=10)
    r = client.post(f"/api/orders/{d['id']}/cancel")
    assert r.status_code == 200
    db.expire_all()
    order = db.get(Order, d["id"])
    assert order.status == "CANCELLED" and order.cancel_reason == "用户取消"
    assert db.query(Product).first().stock == 10  # 回补


def test_cancel_done_conflict(client, db):
    d = make_order(client, db)
    order = db.get(Order, d["id"])
    order.status, order.done_at = "DONE", datetime.now()
    db.commit()
    r = client.post(f"/api/orders/{d['id']}/cancel")
    assert r.status_code == 409 and "已核销" not in r.json()["detail"]  # 状态提示文案
    assert "取消" in r.json()["detail"]


def test_cancel_ready_ok(client, db):
    d = make_order(client, db)
    order = db.get(Order, d["id"])
    order.status, order.ready_at = "READY", datetime.now()
    db.commit()
    assert client.post(f"/api/orders/{d['id']}/cancel").status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_order_cancel.py -v`
Expected: FAIL（404 路由不存在）

- [ ] **Step 3: 实现**

`backend/app/services/orders.py` 追加：

```python
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
            p = db.get(Product, it.product_id)
            if p is not None and p.stock is not None:
                p.stock += it.qty  # 有限库存回补
    db.commit()
    return db.get(Order, order.id)
```

同文件顶部补充：

```python
STATUS_LABELS = {"PENDING": "待备货", "READY": "待取货", "DONE": "已完成", "CANCELLED": "已取消"}
```

（与 serializers.STATUS_LABEL 保持一致；直接 `from app.serializers import STATUS_LABEL as STATUS_LABELS` 亦可。）

`backend/app/routers/orders.py` 追加：

```python
from fastapi import Query
from app.models import Order
from app.services.orders import cancel_order


def _my_order(db: Session, user: User, oid: int) -> Order:
    o = db.get(Order, oid)
    if not o or o.user_id != user.id:
        raise AppError(404, "订单不存在")
    return o


@router.get("")
def my_orders(status: str | None = None, page: int = Query(1, ge=1),
              user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Order).filter(Order.user_id == user.id)
    if status:
        q = q.filter(Order.status == status)
    total = q.count()
    rows = (q.order_by(Order.id.desc()).offset((page - 1) * 20).limit(20).all())
    return {"items": [order_to_dict(o) for o in rows], "total": total, "page": page}


@router.get("/{oid}")
def my_order_detail(oid: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    return order_to_dict(_my_order(db, user, oid))


@router.post("/{oid}/cancel")
def my_order_cancel(oid: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    o = _my_order(db, user, oid)
    cancel_order(db, o, "用户取消")
    return {"ok": True}
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_order_cancel.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 我的订单查询与取消（条件更新+库存回补）"
```

---

### Task 9: 商品管理 API（后台 CRUD + 分类 + 图片上传）

**Files:**
- Create: `backend/app/routers/admin_products.py`
- Modify: `backend/app/main.py`（挂路由 + 静态 /uploads）
- Test: `backend/tests/test_admin_products.py`

**Interfaces:**
- Consumes: `get_current_admin`、`product_to_dict`
- Produces: `GET/POST /api/admin/products`、`PUT /api/admin/products/{id}`（含 status/stock 任意更新）、`GET/POST/PUT /api/admin/categories`、`POST /api/admin/upload`（multipart `file` → `{url}`）；静态目录 `{settings.upload_dir}` 挂载在 `/uploads`

- [ ] **Step 1: 写失败测试** `backend/tests/test_admin_products.py`

```python
import io
import zlib

from app.models import Admin
from app.utils.security import hash_password


def png_bytes(size_kb=1):
    return b"\x89PNG\r\n\x1a\n" + zlib.compress(b"0" * size_kb * 1024)


def admin_login(client, db, role="super"):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role=role, name="管"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def test_create_update_product(client, db):
    admin_login(client, db)
    r = client.post("/api/admin/products", json={
        "name": "测试米", "spec": "5kg", "unit": "袋",
        "price_original": 6750, "price_sale": 6620, "stock": 5})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.put(f"/api/admin/products/{pid}", json={"price_sale": 6000, "status": "off"})
    assert r.json()["price_sale"] == 6000 and r.json()["status"] == "off"


def test_requires_admin(client, db):
    assert client.get("/api/admin/products").status_code == 401


def test_upload_rejects_txt_and_oversize(client, db, tmp_path):
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 400
    big = png_bytes(size_kb=6000)  # >5MB
    r = client.post("/api/admin/upload",
                    files={"file": ("b.png", io.BytesIO(big), "image/png")})
    assert r.status_code == 400


def test_upload_png_ok(client, db):
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("c.png", io.BytesIO(png_bytes()), "image/png")})
    assert r.status_code == 200
    assert r.json()["url"].startswith("/uploads/") and r.json()["url"].endswith(".png")


def test_category_crud(client, db):
    admin_login(client, db)
    cid = client.post("/api/admin/categories", json={"name": "蛋品"}).json()["id"]
    r = client.put(f"/api/admin/categories/{cid}", json={"name": "糖蜜蛋品", "enabled": True})
    assert r.json()["name"] == "糖蜜蛋品"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_admin_products.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/routers/admin_products.py`:

```python
import os
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, Category, Product
from app.serializers import product_to_dict

router = APIRouter(prefix="/api/admin", tags=["admin-products"],
                   dependencies=[Depends(get_current_admin)])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD = 5 * 1024 * 1024


class ProductIn(BaseModel):
    name: str
    spec: str = ""
    unit: str = "件"
    brand: str = ""
    origin: str = ""
    category_id: int | None = None
    price_original: int
    price_sale: int
    stock: int | None = None
    sort: int = 0
    status: str = "on"
    image: str | None = None


@router.get("/products")
def admin_products(q: str | None = None, category_id: int | None = None,
                   status: str | None = None, page: int = Query(1, ge=1),
                   db: Session = Depends(get_db)):
    query = db.query(Product)
    if q:
        query = query.filter(Product.name.contains(q))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status:
        query = query.filter(Product.status == status)
    total = query.count()
    rows = (query.order_by(Product.sort, Product.id)
            .offset((page - 1) * 20).limit(20).all())
    return {"items": [product_to_dict(p) for p in rows], "total": total, "page": page}


@router.post("/products")
def create_product(body: ProductIn, db: Session = Depends(get_db)):
    _validate(body)
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    return product_to_dict(p)


@router.put("/products/{pid}")
def update_product(pid: int, body: ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise AppError(404, "商品不存在")
    _validate(body)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return product_to_dict(p)


def _validate(body: ProductIn):
    if body.price_sale <= 0 or body.price_original <= 0:
        raise AppError(400, "价格必须大于 0（单位：分）")
    if body.status not in ("on", "off"):
        raise AppError(400, "status 只能是 on/off")
    if body.stock is not None and body.stock < 0:
        raise AppError(400, "库存不能为负")


class CategoryIn(BaseModel):
    name: str
    sort: int = 0
    enabled: bool = True


@router.get("/categories")
def admin_categories(db: Session = Depends(get_db)):
    rows = db.query(Category).order_by(Category.sort, Category.id).all()
    return [{"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}
            for c in rows]


@router.post("/categories")
def create_category(body: CategoryIn, db: Session = Depends(get_db)):
    if db.query(Category).filter_by(name=body.name).first():
        raise AppError(400, "分类已存在")
    c = Category(**body.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}


@router.put("/categories/{cid}")
def update_category(cid: int, body: CategoryIn, db: Session = Depends(get_db)):
    c = db.get(Category, cid)
    if not c:
        raise AppError(404, "分类不存在")
    c.name, c.sort, c.enabled = body.name, body.sort, body.enabled
    db.commit()
    return {"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}


@router.post("/upload")
async def upload(file: UploadFile):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise AppError(400, "仅支持 jpg/png/webp 图片")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise AppError(400, "图片不能超过 5MB")
    os.makedirs(settings.upload_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, name), "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{name}"}
```

`backend/app/main.py`：挂路由 + 静态目录（在 include_router 区追加）：

```python
    from app.routers.admin_products import router as admin_products_router
    app.include_router(admin_products_router)

    from fastapi.staticfiles import StaticFiles
    from app.config import settings
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_admin_products.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 后台商品/分类管理与图片上传"
```

---

### Task 10: Excel 导入导出（模板/导入/商品导出）

**Files:**
- Create: `backend/app/services/excel.py`、`backend/app/routers/admin_excel.py`
- Modify: `backend/app/main.py`（挂路由）
- Test: `backend/tests/test_excel.py`

**Interfaces:**
- Consumes: `Product/Category`、`get_current_admin`
- Produces: `build_product_template() -> Workbook`、`import_products_xlsx(db, fileobj) -> {created, updated, errors:[{row,msg}]}`、`export_products_xlsx(db) -> Workbook`（services/excel.py，E2E 与管理端复用）；`GET /api/admin/products/template`（xlsx 下载）、`POST /api/admin/products/import`（multipart `file`）、`GET /api/admin/products/export`
- 模板列（第 1 行表头）：`商品名称 规格 单位 品牌 产地 分类 原价(元) 售价(元) 库存(空=无限) 排序`；导入按 `商品名称+规格` 匹配更新

- [ ] **Step 1: 写失败测试** `backend/tests/test_excel.py`

```python
import io

from openpyxl import Workbook

from app.models import Admin, Product
from app.utils.security import hash_password


def admin_login(client, db):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def xlsx_file(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["商品名称", "规格", "单位", "品牌", "产地", "分类",
               "原价(元)", "售价(元)", "库存(空=无限)", "排序"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_template_download(client, db):
    admin_login(client, db)
    r = client.get("/api/admin/products/template")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]


def test_import_creates_and_reports_errors(client, db):
    admin_login(client, db)
    buf = xlsx_file([
        ["新米", "5kg", "袋", "", "", "粮油米面", 67.5, 66.2, "", 1],   # OK
        ["", "1kg", "瓶", "", "", "", 10, 9, "", ""],                  # 缺名称
        ["坏价", "1kg", "瓶", "", "", "", "abc", 9, "", ""],           # 价格非数字
    ])
    r = client.post("/api/admin/products/import",
                    files={"file": ("import.xlsx", buf,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    d = r.json()
    assert d["created"] == 1
    assert len(d["errors"]) == 2
    assert d["errors"][0]["row"] == 3            # Excel 行号（含表头）
    assert db.query(Product).filter_by(name="新米").count() == 1


def test_import_updates_by_name_spec(client, db):
    admin_login(client, db)
    db.add(Product(name="新米", spec="5kg", unit="袋", price_original=6750,
                   price_sale=6620))
    db.commit()
    buf = xlsx_file([["新米", "5kg", "袋", "", "", "", 67.5, 60.0, 8, ""]])
    d = client.post("/api/admin/products/import",
                    files={"file": ("i.xlsx", buf,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert d["updated"] == 1 and d["created"] == 0
    p = db.query(Product).filter_by(name="新米").first()
    assert p.price_sale == 6000 and p.stock == 8


def test_export_contains_all(client, db):
    admin_login(client, db)
    db.add(Product(name="米A", spec="1kg", unit="袋", price_original=100, price_sale=90))
    db.commit()
    r = client.get("/api/admin/products/export")
    assert r.status_code == 200 and len(r.content) > 500
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_excel.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/services/excel.py`:

```python
from io import BytesIO

from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from app.models import Category, Product

HEADERS = ["商品名称", "规格", "单位", "品牌", "产地", "分类",
           "原价(元)", "售价(元)", "库存(空=无限)", "排序"]


def _to_cents(v) -> int | None:
    if v is None or v == "":
        return None
    return int(round(float(v) * 100))


def build_product_template() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "商品导入"
    ws.append(HEADERS)
    return wb


def import_products_xlsx(db: Session, fileobj) -> dict:
    wb = load_workbook(fileobj, data_only=True)
    ws = wb.active
    created = updated = 0
    errors: list[dict] = []
    cats: dict[str, Category] = {}
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        try:
            name = str(row[0] or "").strip()
            spec = str(row[1] or "").strip()
            if not name:
                raise ValueError("商品名称不能为空")
            po, ps = _to_cents(row[6]), _to_cents(row[7])
            if po is None or ps is None:
                raise ValueError("原价/售价必须为数字")
            stock = None if row[8] in (None, "") else int(row[8])
            cat_name = str(row[5] or "").strip()
            cat_id = None
            if cat_name:
                if cat_name not in cats:
                    c = db.query(Category).filter_by(name=cat_name).first()
                    if not c:
                        c = Category(name=cat_name, sort=99)
                        db.add(c)
                        db.flush()
                    cats[cat_name] = c
                cat_id = cats[cat_name].id
            p = db.query(Product).filter_by(name=name, spec=spec).first()
            fields = dict(unit=str(row[2] or "件"), brand=str(row[3] or ""),
                          origin=str(row[4] or ""), category_id=cat_id,
                          price_original=po, price_sale=ps, stock=stock,
                          sort=int(row[9]) if row[9] not in (None, "") else 0)
            if p:
                for k, v in fields.items():
                    setattr(p, k, v)
                updated += 1
            else:
                db.add(Product(name=name, spec=spec, status="on", **fields))
                created += 1
        except Exception as e:  # 行级错误不阻断整体
            db.rollback()
            errors.append({"row": i, "msg": str(e)})
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}


def export_products_xlsx(db: Session) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "商品"
    ws.append(HEADERS + ["状态", "id"])
    for p in db.query(Product).order_by(Product.sort, Product.id).all():
        ws.append([p.name, p.spec, p.unit, p.brand, p.origin,
                   p.category.name if p.category_id else "",
                   p.price_original / 100, p.price_sale / 100,
                   "" if p.stock is None else p.stock, p.sort,
                   "在售" if p.status == "on" else "下架", p.id])
    return wb


def workbook_response(wb: Workbook, filename: str):
    from fastapi.responses import StreamingResponse
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

（`p.category.name` 需要在 Product 上加 relationship；在 models.py 的 Product 内追加：`category = relationship("Category")`。）

`backend/app/routers/admin_excel.py`:

```python
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Admin, AdminLog
from app.services.excel import (build_product_template, export_products_xlsx,
                                import_products_xlsx, workbook_response)

router = APIRouter(prefix="/api/admin/products", tags=["admin-excel"],
                   dependencies=[Depends(get_current_admin)])


@router.get("/template")
def template():
    return workbook_response(build_product_template(), "商品导入模板.xlsx")


@router.post("/import")
async def import_excel(file: UploadFile, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    result = import_products_xlsx(db, file.file)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="import",
                    target="products", detail=f"新增{result['created']} 更新{result['updated']}"))
    db.commit()
    return result


@router.get("/export")
def export(db: Session = Depends(get_db)):
    return workbook_response(export_products_xlsx(db), "商品导出.xlsx")
```

`backend/app/main.py` 追加：

```python
    from app.routers.admin_excel import router as admin_excel_router
    app.include_router(admin_excel_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_excel.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 商品 Excel 模板/导入/导出（行级错误报告）"
```

---

### Task 11: 订单管理 API（检索/批量备货/代取消/备货清单）

**Files:**
- Create: `backend/app/routers/admin_orders.py`
- Modify: `backend/app/services/orders.py`（追加 mark_ready）
- Test: `backend/tests/test_admin_orders.py`

**Interfaces:**
- Consumes: `cancel_order`、`order_to_dict(include_user=True)`
- Produces: `mark_ready(db, order) -> Order`（PENDING→READY 条件更新）；`GET /api/admin/orders?status=&date_from=&date_to=&q=&page=`（q 匹配 订单号/工号/姓名/取货码）；`POST /api/admin/orders/ready {ids:[...]}` → `{updated, failed:[{id,detail}]}`；`POST /api/admin/orders/{id}/cancel {reason}`；`GET /api/admin/orders/picking-list.xlsx`（两 sheet：按商品汇总 / 按订单明细，取 PENDING+READY）

- [ ] **Step 1: 写失败测试** `backend/tests/test_admin_orders.py`

```python
from datetime import datetime, timedelta

from app.models import Admin, Order, Product
from app.utils.security import hash_password


def setup_(client, db, n=2):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    p = Product(name="米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on")
    db.add_all([p])
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    order_ids = []
    for i in range(n):
        client.get(f"/api/auth/dev-login?empid=T00{i}&name=老师{i}")
        r = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": 1 + i}]})
        order_ids.append(r.json()["id"])
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    return order_ids


def test_search_by_code_and_empid(client, db):
    ids = setup_(client, db)
    code = db.get(Order, ids[0]).pickup_code
    assert client.get(f"/api/admin/orders?q={code}").json()["total"] == 1
    assert client.get("/api/admin/orders?q=T001").json()["total"] == 1
    assert client.get("/api/admin/orders?status=PENDING").json()["total"] == 2


def test_batch_ready(client, db):
    ids = setup_(client, db)
    r = client.post("/api/admin/orders/ready", json={"ids": ids + [99999]})
    d = r.json()
    assert d["updated"] == 2 and d["failed"][0]["id"] == 99999
    assert db.get(Order, ids[0]).status == "READY"


def test_ready_idempotent_reports_failed(client, db):
    ids = setup_(client, db, n=1)
    client.post("/api/admin/orders/ready", json={"ids": ids})
    d = client.post("/api/admin/orders/ready", json={"ids": ids}).json()
    assert d["updated"] == 0 and len(d["failed"]) == 1  # 已是 READY，报告原因


def test_admin_cancel_with_reason(client, db):
    ids = setup_(client, db, n=1)
    r = client.post(f"/api/admin/orders/{ids[0]}/cancel", json={"reason": "缺货"})
    assert r.status_code == 200
    o = db.get(Order, ids[0])
    assert o.status == "CANCELLED" and o.cancel_reason == "缺货"


def test_picking_list_xlsx(client, db):
    setup_(client, db)
    r = client.get("/api/admin/orders/picking-list.xlsx")
    assert r.status_code == 200 and len(r.content) > 1000
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_admin_orders.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/services/orders.py` 追加：

```python
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
```

`backend/app/routers/admin_orders.py`:

```python
from datetime import datetime, time, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, Order, OrderItem, User
from app.serializers import order_to_dict
from app.services.orders import cancel_order, mark_ready

router = APIRouter(prefix="/api/admin/orders", tags=["admin-orders"],
                   dependencies=[Depends(get_current_admin)])


@router.get("")
def admin_orders(status: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 q: str | None = None, page: int = Query(1, ge=1),
                 db: Session = Depends(get_db)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if date_from:
        query = query.filter(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Order.created_at
                             < datetime.fromisoformat(date_to) + timedelta(days=1))
    if q:
        like = f"%{q}%"
        query = (query.join(User, Order.user_id == User.id)
                 .filter(or_(Order.order_no.like(like), Order.pickup_code.like(like),
                             User.empid.like(like), User.name.like(like))))
    total = query.count()
    rows = (query.order_by(Order.id.desc()).offset((page - 1) * 20).limit(20).all())
    return {"items": [order_to_dict(o, include_user=True) for o in rows],
            "total": total, "page": page}


class ReadyIn(BaseModel):
    ids: list[int]


@router.post("/ready")
def batch_ready(body: ReadyIn, db: Session = Depends(get_db)):
    updated, failed = 0, []
    for oid in body.ids:
        o = db.get(Order, oid)
        if not o:
            failed.append({"id": oid, "detail": "订单不存在"})
            continue
        try:
            mark_ready(db, o)
            updated += 1
        except AppError as e:
            failed.append({"id": oid, "detail": e.msg})
    return {"updated": updated, "failed": failed}


class CancelIn(BaseModel):
    reason: str


@router.post("/{oid}/cancel")
def admin_cancel(oid: int, body: CancelIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    o = db.get(Order, oid)
    if not o:
        raise AppError(404, "订单不存在")
    cancel_order(db, o, f"管理员取消：{body.reason}", by_admin=True)
    from app.models import AdminLog
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="cancel",
                    target=o.order_no, detail=body.reason))
    db.commit()
    return {"ok": True}


@router.get("/picking-list.xlsx")
def picking_list(db: Session = Depends(get_db)):
    orders = (db.query(Order)
              .filter(Order.status.in_(["PENDING", "READY"]))
              .order_by(Order.id).all())
    wb = Workbook()
    ws = wb.active
    ws.title = "按商品汇总"
    ws.append(["商品名称", "规格", "单位", "合计数量"])
    agg: dict[tuple, int] = {}
    for o in orders:
        for it in o.items:
            k = (it.p_name, it.p_spec, it.p_unit)
            agg[k] = agg.get(k, 0) + it.qty
    for (n, s, u), qty in sorted(agg.items()):
        ws.append([n, s, u, qty])
    ws2 = wb.create_sheet("按订单明细")
    ws2.append(["订单号", "状态", "工号", "姓名", "商品", "数量", "总额(元)", "备注", "下单时间"])
    from app.serializers import STATUS_LABEL
    for o in orders:
        items_text = "；".join(f"{i.p_name}×{i.qty}" for i in o.items)
        ws2.append([o.order_no, STATUS_LABEL[o.status], o.user.empid, o.user.name or "",
                    items_text, sum(i.qty for i in o.items), o.total / 100,
                    o.remark, o.created_at.strftime("%m-%d %H:%M")])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=picking-list.xlsx"})
```

`backend/app/main.py` 追加：

```python
    from app.routers.admin_orders import router as admin_orders_router
    app.include_router(admin_orders_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_admin_orders.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 后台订单管理（检索/批量备货/代取消/备货清单）"
```

---

### Task 12: 核销 API

**Files:**
- Create: `backend/app/routers/admin_verify.py`
- Test: `backend/tests/test_verify.py`

**Interfaces:**
- Consumes: `order_to_dict(include_user=True)`、`AdminLog`
- Produces: `parse_code(raw) -> str`（兼容裸取货码与二维码串 `SC:{order_no}:{code}`）；`GET /api/admin/verify/{raw}`（订单摘要 + 可核销标志）；`POST /api/admin/verify/{raw}`（READY→DONE，记录核销人与时间；状态不符 409，未知码 404）

- [ ] **Step 1: 写失败测试** `backend/tests/test_verify.py`

```python
from datetime import datetime

from app.models import Admin, Order, Product
from app.utils.security import hash_password


def setup_(client, db, status="READY"):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    p = Product(name="米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on")
    db.add_all([p])
    db.commit()
    client.get("/api/auth/dev-login?empid=T001&name=张老师")
    d = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": 2}]}).json()
    if status != "PENDING":
        o = db.get(Order, d["id"])
        o.status = status
        if status == "DONE":
            o.done_at = datetime.now()
        db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    return d


def test_lookup_by_code_and_qr(client, db):
    d = setup_(client, db)
    r = client.get(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 200 and r.json()["order"]["id"] == d["id"]
    qr = f"SC:{d['order_no']}:{d['pickup_code']}"
    assert client.get(f"/api/admin/verify/{qr}").json()["order"]["id"] == d["id"]


def test_verify_ok_records_admin(client, db):
    d = setup_(client, db)
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 200
    o = db.get(Order, d["id"])
    assert o.status == "DONE" and o.done_at and o.verified_by == 1


def test_verify_twice(client, db):
    d = setup_(client, db, status="DONE")
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 409 and "已完成" in r.json()["detail"]


def test_verify_pending_hint(client, db):
    d = setup_(client, db, status="PENDING")
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 409 and "待备货" in r.json()["detail"]


def test_verify_cancelled(client, db):
    d = setup_(client, db, status="CANCELLED")
    assert client.post(f"/api/admin/verify/{d['pickup_code']}").status_code == 409


def test_unknown_code_404(client, db):
    setup_(client, db)
    assert client.post("/api/admin/verify/000001").status_code in (404, 409)
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_verify.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/routers/admin_verify.py`:

```python
import re
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog, Order
from app.serializers import STATUS_LABEL, order_to_dict

router = APIRouter(prefix="/api/admin/verify", tags=["verify"],
                   dependencies=[Depends(get_current_admin)])

QR_RE = re.compile(r"^SC:[0-9-]+:(\d{6})$")


def parse_code(raw: str) -> str:
    m = QR_RE.match(raw.strip())
    return m.group(1) if m else raw.strip()


def _find(db: Session, raw: str) -> Order:
    code = parse_code(raw)
    o = db.query(Order).filter_by(pickup_code=code).first()
    if not o:
        raise AppError(404, f"取货码 {code} 不存在，请核对")
    return o


@router.get("/{raw}")
def lookup(raw: str, db: Session = Depends(get_db)):
    o = _find(db, raw)
    d = order_to_dict(o, include_user=True)
    d["verifiable"] = o.status == "READY"
    return {"order": d}


@router.post("/{raw}")
def verify(raw: str, db: Session = Depends(get_db),
           admin: Admin = Depends(get_current_admin)):
    o = _find(db, raw)
    res = db.execute(
        update(Order)
        .where(Order.id == o.id, Order.status == "READY")
        .values(status="DONE", done_at=datetime.now(), verified_by=admin.id)
    )
    if res.rowcount == 0:
        db.rollback()
        current = db.get(Order, o.id).status
        hint = "，请先做备货完成" if current == "PENDING" else ""
        raise AppError(409, f"订单状态为「{STATUS_LABEL[current]}」，不能核销{hint}")
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="verify",
                    target=o.order_no, detail=f"取货码 {o.pickup_code}"))
    db.commit()
    return order_to_dict(db.get(Order, o.id), include_user=True)
```

`backend/app/main.py` 追加：

```python
    from app.routers.admin_verify import router as admin_verify_router
    app.include_router(admin_verify_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_verify.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 取货码核销（扫码/手输、状态拦截、留痕）"
```

---

### Task 13: 统计与对账 API

**Files:**
- Create: `backend/app/routers/admin_stats.py`
- Test: `backend/tests/test_stats.py`

**Interfaces:**
- Consumes: `Order/OrderItem`
- Produces: `GET /api/admin/stats/dashboard` → `{today_new, pending, ready, today_done_count, today_done_amount, last7:[{date,orders,sales}]}`；`GET /api/admin/stats?date_from=&date_to=` → `{order_count, done_count, done_amount, by_status:{...}, top_products:[{name,qty,amount}]}`；`GET /api/admin/stats/export?date_from=&date_to=`（核销流水 xlsx）

- [ ] **Step 1: 写失败测试** `backend/tests/test_stats.py`

```python
from datetime import datetime, timedelta

from app.models import Admin, Order, User
from app.utils.security import hash_password


def admin_login(client, db):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def make_orders(db, n_done=2, amount=6620):
    u = User(empid="T001", name="张老师")
    db.add(u)
    db.commit()
    for i in range(n_done):
        from app.models import OrderItem, Product
        p = Product(name=f"米{i}", spec="5kg", unit="袋", price_original=6750,
                    price_sale=amount, status="on")
        db.add(p)
        db.flush()
        o = Order(order_no=f"20261118-{i+1:06d}", user_id=u.id, status="DONE",
                  total=amount, pickup_code=f"{100000+i}",
                  done_at=datetime.now(), verified_by=1)
        db.add(o)
        db.flush()
        db.add(OrderItem(order_id=o.id, product_id=p.id, p_name=f"米{i}",
                         p_spec="5kg", p_unit="袋", p_price=amount, qty=1,
                         subtotal=amount))
    db.add(Order(order_no="20261118-000099", user_id=u.id, status="PENDING",
                 total=amount, pickup_code="999999"))
    db.commit()


def test_dashboard(client, db):
    make_orders(db, n_done=2)
    admin_login(client, db)
    d = client.get("/api/admin/stats/dashboard").json()
    assert d["pending"] == 1
    assert d["today_done_count"] == 2
    assert d["today_done_amount"] == 6620 * 2
    assert len(d["last7"]) == 7


def test_range_stats_and_ranking(client, db):
    make_orders(db, n_done=2)
    admin_login(client, db)
    today = datetime.now().strftime("%Y-%m-%d")
    d = client.get(f"/api/admin/stats?date_from={today}&date_to={today}").json()
    assert d["done_count"] == 2 and d["done_amount"] == 13240
    assert d["top_products"][0]["name"] == "米0"


def test_export_xlsx(client, db):
    make_orders(db, n_done=1)
    admin_login(client, db)
    today = datetime.now().strftime("%Y-%m-%d")
    r = client.get(f"/api/admin/stats/export?date_from={today}&date_to={today}")
    assert r.status_code == 200 and len(r.content) > 1000
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_stats.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/routers/admin_stats.py`:

```python
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Admin, Order, OrderItem

router = APIRouter(prefix="/api/admin/stats", tags=["stats"],
                   dependencies=[Depends(get_current_admin)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    now = datetime.now()
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow0 = today0 + timedelta(days=1)
    done_today = (db.query(Order)
                  .filter(Order.status == "DONE", Order.done_at >= today0,
                          Order.done_at < tomorrow0).all())
    last7 = []
    for i in range(6, -1, -1):
        d0 = today0 - timedelta(days=i)
        d1 = d0 + timedelta(days=1)
        orders = db.query(Order).filter(Order.created_at >= d0,
                                        Order.created_at < d1).count()
        sales = sum(o.total for o in db.query(Order)
                    .filter(Order.status == "DONE", Order.done_at >= d0,
                            Order.done_at < d1).all())
        last7.append({"date": d0.strftime("%m-%d"), "orders": orders,
                      "sales": sales})
    return {
        "today_new": db.query(Order).filter(Order.created_at >= today0,
                                            Order.created_at < tomorrow0).count(),
        "pending": db.query(Order).filter_by(status="PENDING").count(),
        "ready": db.query(Order).filter_by(status="READY").count(),
        "today_done_count": len(done_today),
        "today_done_amount": sum(o.total for o in done_today),
        "last7": last7,
    }


def _range_done(db: Session, date_from: str, date_to: str):
    d0 = datetime.fromisoformat(date_from)
    d1 = datetime.fromisoformat(date_to) + timedelta(days=1)
    return (d0, d1,
            db.query(Order).filter(Order.status == "DONE", Order.done_at >= d0,
                                   Order.done_at < d1).all())


@router.get("")
def range_stats(date_from: str, date_to: str, db: Session = Depends(get_db)):
    d0, d1, done = _range_done(db, date_from, date_to)
    by_status = {"PENDING": 0, "READY": 0, "DONE": 0, "CANCELLED": 0}
    for o in db.query(Order).filter(Order.created_at >= d0, Order.created_at < d1).all():
        by_status[o.status] = by_status.get(o.status, 0) + 1
    agg: dict[str, dict] = {}
    for o in done:
        for it in o.items:
            a = agg.setdefault(it.p_name, {"name": it.p_name, "qty": 0, "amount": 0})
            a["qty"] += it.qty
            a["amount"] += it.subtotal
    top = sorted(agg.values(), key=lambda x: -x["qty"])[:10]
    return {"order_count": sum(by_status.values()), "done_count": len(done),
            "done_amount": sum(o.total for o in done), "by_status": by_status,
            "top_products": top}


@router.get("/export")
def export(date_from: str, date_to: str, db: Session = Depends(get_db)):
    _, _, done = _range_done(db, date_from, date_to)
    wb = Workbook()
    ws = wb.active
    ws.title = "核销流水"
    ws.append(["取货时间", "订单号", "取货码", "工号", "姓名",
               "商品明细", "总额(元)", "核销人"])
    admins = {a.id: a.username for a in db.query(Admin).all()}
    for o in sorted(done, key=lambda x: x.done_at):
        ws.append([o.done_at.strftime("%Y-%m-%d %H:%M"), o.order_no, o.pickup_code,
                   o.user.empid, o.user.name or "",
                   "；".join(f"{i.p_name}×{i.qty}" for i in o.items),
                   o.total / 100, admins.get(o.verified_by, "")])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reconciliation.xlsx"})
```

`backend/app/main.py` 追加：

```python
    from app.routers.admin_stats import router as admin_stats_router
    app.include_router(admin_stats_router)
```

- [ ] **Step 4: 运行测试通过**

Run: `cd backend && pytest tests/test_stats.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: 工作台统计与核销流水对账导出"
```

---

### Task 14: 系统设置（管理员账号/须知/操作日志）

**Files:**
- Create: `backend/app/routers/admin_settings.py`、`backend/app/routers/public.py`
- Test: `backend/tests/test_admin_settings.py`

**Interfaces:**
- Consumes: `require_super`、`hash_password`、`Setting/AdminLog`
- Produces: `GET/POST /api/admin/admins`、`PUT /api/admin/admins/{id}`（重置密码/角色/停用，均超管）；`GET /api/admin/logs?page=`（超管）；`GET/PUT /api/admin/settings/notice`（超管，`{content}`）；公开 `GET /api/notice`（教职工取须知，登录态）

- [ ] **Step 1: 写失败测试** `backend/tests/test_admin_settings.py`

```python
from app.models import Admin, Setting
from app.utils.security import hash_password, verify_password


def super_login(client, db):
    db.add(Admin(username="root", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "root", "password": "p"})


def test_create_admin_then_login(client, db):
    super_login(client, db)
    r = client.post("/api/admin/admins", json={
        "username": "op1", "password": "op12345", "role": "operator", "name": "操作员"})
    assert r.status_code == 200
    client.post("/api/admin/auth/logout")
    r = client.post("/api/admin/auth/login", json={"username": "op1", "password": "op12345"})
    assert r.status_code == 200


def test_operator_cannot_manage(client, db):
    super_login(client, db)
    client.post("/api/admin/admins",
                json={"username": "op", "password": "x12345", "role": "operator"})
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "op", "password": "x12345"})
    assert client.get("/api/admin/admins").status_code == 403


def test_reset_password_and_disable(client, db):
    super_login(client, db)
    aid = client.post("/api/admin/admins", json={
        "username": "op2", "password": "old123", "role": "operator"}).json()["id"]
    client.put(f"/api/admin/admins/{aid}", json={"password": "new123"})
    client.post("/api/admin/auth/logout")
    assert client.post("/api/admin/auth/login",
                       json={"username": "op2", "password": "new123"}).status_code == 200
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "root", "password": "p"})
    client.put(f"/api/admin/admins/{aid}", json={"is_active": False})
    client.post("/api/admin/auth/logout")
    assert client.post("/api/admin/auth/login",
                       json={"username": "op2", "password": "new123"}).status_code == 403


def test_notice_roundtrip(client, db):
    super_login(client, db)
    client.put("/api/admin/settings/notice",
               json={"content": "服务点：综合楼一层\n时间：工作日 14:00-17:00"})
    client.get("/api/auth/dev-login?empid=T001")
    r = client.get("/api/notice")
    assert r.status_code == 200
    assert "综合楼一层" in r.json()["content"]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_admin_settings.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`backend/app/routers/admin_settings.py`:

```python
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin, require_super
from app.exceptions import AppError
from app.models import Admin, AdminLog, Setting
from app.utils.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin-settings"])


@router.get("/admins", dependencies=[Depends(require_super)])
def list_admins(db: Session = Depends(get_db)):
    rows = db.query(Admin).order_by(Admin.id).all()
    return [{"id": a.id, "username": a.username, "role": a.role, "name": a.name,
             "is_active": a.is_active, "last_login_at":
             a.last_login_at.isoformat() if a.last_login_at else None}
            for a in rows]


class AdminIn(BaseModel):
    username: str
    password: str
    role: str = "operator"
    name: str = ""


@router.post("/admins", dependencies=[Depends(require_super)])
def create_admin(body: AdminIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    if body.role not in ("super", "operator"):
        raise AppError(400, "角色不合法")
    if len(body.password) < 6:
        raise AppError(400, "密码至少 6 位")
    if db.query(Admin).filter_by(username=body.username).first():
        raise AppError(400, "用户名已存在")
    a = Admin(username=body.username, password_hash=hash_password(body.password),
              role=body.role, name=body.name)
    db.add(a)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="admin_create",
                    target=body.username))
    db.commit()
    return {"id": a.id, "username": a.username, "role": a.role}


class AdminUpdateIn(BaseModel):
    password: str | None = None
    role: str | None = None
    name: str | None = None
    is_active: bool | None = None


@router.put("/admins/{aid}", dependencies=[Depends(require_super)])
def update_admin(aid: int, body: AdminUpdateIn, db: Session = Depends(get_db),
                 admin: Admin = Depends(get_current_admin)):
    a = db.get(Admin, aid)
    if not a:
        raise AppError(404, "账号不存在")
    if body.password:
        a.password_hash = hash_password(body.password)
        a.failed_attempts, a.locked_until = 0, None
    if body.role:
        a.role = body.role
    if body.name is not None:
        a.name = body.name
    if body.is_active is not None:
        a.is_active = body.is_active
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="admin_update",
                    target=a.username, detail=str(body.model_dump(exclude={"password"}))))
    db.commit()
    return {"ok": True}


@router.get("/logs", dependencies=[Depends(require_super)])
def list_logs(page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    q = db.query(AdminLog)
    total = q.count()
    rows = q.order_by(AdminLog.id.desc()).offset((page - 1) * 20).limit(20).all()
    return {"items": [{"id": l.id, "username": l.username, "action": l.action,
                       "target": l.target, "detail": l.detail,
                       "created_at": l.created_at.isoformat()} for l in rows],
            "total": total, "page": page}


class NoticeIn(BaseModel):
    content: str


def get_notice(db: Session) -> str:
    s = db.get(Setting, "notice_content")
    return s.value if s else ""


@router.get("/settings/notice", dependencies=[Depends(require_super)])
def read_notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}


@router.put("/settings/notice", dependencies=[Depends(require_super)])
def write_notice(body: NoticeIn, db: Session = Depends(get_db)):
    s = db.get(Setting, "notice_content")
    if not s:
        s = Setting(key="notice_content")
        db.add(s)
    s.value = body.content
    db.commit()
    return {"ok": True}
```

`backend/app/routers/public.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.admin_settings import get_notice

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/notice")
def notice(db: Session = Depends(get_db)):
    return {"content": get_notice(db)}
```

（`/api/notice` 不挂 `get_current_user`——须知为非敏感内容，免登录可读，前端登录跳转期间也能展示。）

`backend/app/main.py` 追加：

```python
    from app.routers.admin_settings import router as admin_settings_router
    from app.routers.public import router as public_router
    app.include_router(admin_settings_router)
    app.include_router(public_router)
```

- [ ] **Step 4: 运行测试通过（并收紧 Task 5 的宽断言）**

Run: `cd backend && pytest tests/test_admin_settings.py tests/test_admin_auth.py -v`
Expected: 全部 passed。随后把 `tests/test_admin_auth.py::test_require_super_blocks_operator` 中 `assert r.status_code in (403, 404)` 改为 `assert r.status_code == 403`，重跑确认仍通过。

- [ ] **Step 5: 后端全量测试与覆盖率**

Run: `cd backend && pytest --cov=app --cov-report=term`
Expected: 全部通过，`app` 覆盖率 ≥80%

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: 管理员账号/须知/操作日志与公开须知接口"
```

---

### Task 15: H5 壳、登录态与取货须知

**Files:**
- Create: `frontend/src/stores/user.ts`、`frontend/src/mobile/MobileLayout.vue`、`frontend/src/mobile/views/NoticeView.vue`
- Modify: `frontend/src/router/index.ts`（布局路由+守卫）、`frontend/src/mobile/views/HomeView.vue`（挂到布局下，内容仍是占位）
- Test: 手动验证（本任务无新逻辑单测；登录态逻辑由 E2E Task 25 覆盖）

**Interfaces:**
- Consumes: `api`（Task 3）、CAS 跳转 `/api/auth/cas/login`
- Produces: `useUserStore`（`{user, checked, fetch()}`，后续页面复用）；路由守卫规则：`/m/*` 未登录 → 302 CAS，`/admin/*` 未登录 → `/admin/login`；MobileLayout（tabbar：首页/我的订单/取货须知）

- [ ] **Step 1: 实现用户 store** `frontend/src/stores/user.ts`

```ts
import { defineStore } from "pinia";
import { api } from "../api/http";

export const useUserStore = defineStore("user", {
  state: () => ({ user: null as any, checked: false }),
  actions: {
    async fetch() {
      try {
        this.user = await api("/api/auth/me");
      } catch {
        this.user = null;
      }
      this.checked = true;
    },
  },
});
```

- [ ] **Step 2: 实现布局与须知页**

`frontend/src/mobile/MobileLayout.vue`:

```vue
<template>
  <div class="mobile-wrap">
    <router-view />
    <van-tabbar route>
      <van-tabbar-item to="/m" icon="shop-o">商品</van-tabbar-item>
      <van-tabbar-item to="/m/orders" icon="orders-o">我的订单</van-tabbar-item>
      <van-tabbar-item to="/m/notice" icon="bookmark-o">取货须知</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<style>
.mobile-wrap { max-width: 640px; margin: 0 auto; min-height: 100vh; padding-bottom: 60px; }
</style>
```

`frontend/src/mobile/views/NoticeView.vue`:

```vue
<template>
  <div class="p-4">
    <h3 class="text-lg font-bold mb-2">取货须知</h3>
    <p class="whitespace-pre-wrap leading-6 text-sm">{{ content || "暂无" }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "../../api/http";

const content = ref("");
onMounted(async () => {
  const d = await api("/api/notice");
  content.value = d.content;
});
</script>
```

- [ ] **Step 3: 路由守卫**（`frontend/src/router/index.ts` 全量替换）

```ts
import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "../stores/user";
import { useAdminStore } from "../stores/admin";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/m" },
    {
      path: "/m",
      component: () => import("../mobile/MobileLayout.vue"),
      children: [
        { path: "", component: () => import("../mobile/views/HomeView.vue") },
        { path: "orders", component: () => import("../mobile/views/OrdersView.vue") },
        { path: "order/:id", component: () => import("../mobile/views/OrderDetailView.vue") },
        { path: "notice", component: () => import("../mobile/views/NoticeView.vue") },
      ],
    },
    { path: "/admin/login", component: () => import("../admin/views/LoginView.vue") },
    { path: "/admin", redirect: "/admin/dashboard" },
  ],
});

router.beforeEach(async (to) => {
  if (to.path.startsWith("/admin")) {
    const a = useAdminStore();
    if (to.path === "/admin/login") return true;
    if (!a.checked) await a.fetch();
    if (!a.admin) return "/admin/login";
    return true;
  }
  if (to.path.startsWith("/m")) {
    const u = useUserStore();
    if (!u.checked) await u.fetch();
    if (!u.user) {
      window.location.href = "/api/auth/cas/login"; // CAS 静默往返
      return false;
    }
  }
  return true;
});

export default router;
```

同时创建 `frontend/src/stores/admin.ts`（Task 19 完整使用，此处先建避免编译错误）：

```ts
import { defineStore } from "pinia";
import { api } from "../api/http";

export const useAdminStore = defineStore("admin", {
  state: () => ({ admin: null as any, checked: false }),
  actions: {
    async fetch() {
      try {
        this.admin = await api("/api/admin/auth/me");
      } catch {
        this.admin = null;
      }
      this.checked = true;
    },
    async login(username: string, password: string) {
      this.admin = await api("/api/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      this.checked = true;
    },
    async logout() {
      await api("/api/admin/auth/logout", { method: "POST" });
      this.admin = null;
    },
  },
});
```

路由引用了尚未创建的 `OrderDetailView.vue`，本任务先创建占位（`<template><div>建设中</div></template>`），Task 18 替换。

- [ ] **Step 4: 手动验证 + 构建**

```bash
cd backend && . .venv/bin/activate && DATABASE_URL=sqlite:///./dev.db python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 13000 &
cd frontend && npm run dev
```

浏览器访问 `http://10.204.0.146:5173/m` → 因未登录应跳 CAS（本地未配 CAS 时会 500，属预期）；访问 `http://10.204.0.146:13000/api/auth/dev-login?empid=T001&name=张老师` 后再开 5173/m → 能进入页面并显示 tabbar。`npm run build` 通过。

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: H5 壳与登录守卫（CAS 跳转/须知页）"
```

---

### Task 16: 首页与商品详情（cart store TDD）

**Files:**
- Create: `frontend/src/stores/cart.ts`、`frontend/src/mobile/components/ProductCard.vue`、`frontend/src/mobile/views/ProductView.vue`
- Modify: `frontend/src/mobile/views/HomeView.vue`（全量替换）
- Test: `frontend/src/stores/cart.test.ts`

**Interfaces:**
- Consumes: `GET /api/categories`、`GET /api/products`、`GET /api/products/{id}`
- Produces: `useCartStore`（`items: CartItem[]`，`add(product)`、`setQty(id,qty)`、`remove(id)`、`clear()`、getter `totalCents/count`，localStorage 持久化）；`CartItem = {product_id,name,spec,unit,price_sale,image?}`；路由 `/m/product/:id`

- [ ] **Step 1: 写失败测试** `frontend/src/stores/cart.test.ts`

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useCartStore } from "./cart";

const P = { id: 1, name: "大米", spec: "5kg", unit: "袋", price_sale: 6620 };

describe("cart store", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("加购与合计（分）", () => {
    const c = useCartStore();
    c.add(P as any);
    c.add(P as any);
    c.add({ ...P, id: 2, price_sale: 250 } as any);
    expect(c.count).toBe(3);
    expect(c.totalCents).toBe(6620 * 2 + 250);
  });

  it("改数量、删除、清空", () => {
    const c = useCartStore();
    c.add(P as any);
    c.setQty(1, 5);
    expect(c.totalCents).toBe(6620 * 5);
    c.setQty(1, 0); // 数量 0 视为删除
    expect(c.count).toBe(0);
    c.add(P as any);
    c.remove(1);
    expect(c.count).toBe(0);
    c.add(P as any);
    c.clear();
    expect(c.count).toBe(0);
  });

  it("localStorage 持久化", () => {
    const c = useCartStore();
    c.add(P as any);
    const c2 = useCartStore(); // 新实例读同一 storage
    expect(c2.count).toBe(1);
  });
});
```

Run: `cd frontend && npm test`
Expected: FAIL（cart.ts 不存在）

- [ ] **Step 2: 实现 cart store** `frontend/src/stores/cart.ts`

```ts
import { defineStore } from "pinia";

export interface CartItem {
  product_id: number;
  name: string;
  spec: string;
  unit: string;
  price_sale: number; // 分
  image?: string | null;
  qty: number;
}

const KEY = "sc_cart";

function load(): CartItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export const useCartStore = defineStore("cart", {
  state: () => ({ items: load() }),
  getters: {
    count: (s) => s.items.reduce((a, i) => a + i.qty, 0),
    totalCents: (s) => s.items.reduce((a, i) => a + i.price_sale * i.qty, 0),
  },
  actions: {
    save() {
      localStorage.setItem(KEY, JSON.stringify(this.items));
    },
    add(p: any) {
      const f = this.items.find((i) => i.product_id === p.id);
      if (f) f.qty += 1;
      else
        this.items.push({
          product_id: p.id, name: p.name, spec: p.spec, unit: p.unit,
          price_sale: p.price_sale, image: p.image, qty: 1,
        });
      this.save();
    },
    setQty(pid: number, qty: number) {
      this.items = this.items.filter((i) =>
        i.product_id === pid ? (i.qty = Math.min(999, qty)) !== 0 : true);
      this.save();
    },
    remove(pid: number) {
      this.items = this.items.filter((i) => i.product_id !== pid);
      this.save();
    },
    clear() {
      this.items = [];
      this.save();
    },
  },
});
```

Run: `cd frontend && npm test` → 3 passed

- [ ] **Step 3: 实现首页**（`frontend/src/mobile/views/HomeView.vue` 全量替换）

```vue
<template>
  <div>
    <van-search v-model="q" placeholder="搜索食材" @search="load(1)" />
    <van-tabs v-model:active="activeCat" @change="load(1)">
      <van-tab title="全部" :name="0" />
      <van-tab v-for="c in cats" :key="c.id" :title="c.name" :name="c.id" />
    </van-tabs>
    <div class="p-2 grid grid-cols-1 gap-2">
      <ProductCard v-for="p in products" :key="p.id" :p="p" @add="onAdd" />
      <van-empty v-if="!products.length" description="暂无商品" />
    </div>
    <div class="p-3 text-center text-sm text-gray-400">
      共 {{ total }} 件商品
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { showToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import ProductCard from "../components/ProductCard.vue";

const q = ref("");
const activeCat = ref(0);
const cats = ref<any[]>([]);
const products = ref<any[]>([]);
const total = ref(0);
const cart = useCartStore();

function load(page = 1) {
  const params = new URLSearchParams({ page: String(page) });
  if (q.value) params.set("q", q.value);
  if (activeCat.value) params.set("category_id", String(activeCat.value));
  api(`/api/products?${params}`).then((d: any) => {
    products.value = d.items;
    total.value = d.total;
  });
}

function onAdd(p: any) {
  cart.add(p);
  showToast(`已加入购物车（${cart.count} 件）`);
}

onMounted(async () => {
  cats.value = await api("/api/categories");
  load(1);
});
</script>
```

`frontend/src/mobile/components/ProductCard.vue`:

```vue
<template>
  <div class="flex items-center gap-3 p-3 bg-white rounded-lg">
    <img :src="p.image || '/placeholder.png'" class="w-16 h-16 object-cover rounded"
         @error="$event.target.src = '/placeholder.png'" />
    <div class="flex-1 min-w-0">
      <div class="font-medium truncate">{{ p.name }}</div>
      <div class="text-xs text-gray-400">{{ p.spec }} / {{ p.unit }}</div>
      <div class="mt-1">
        <span class="text-red-500 font-bold">￥{{ fmtMoney(p.price_sale) }}</span>
        <span class="ml-1 text-xs text-gray-400 line-through">
          ￥{{ fmtMoney(p.price_original) }}
        </span>
      </div>
    </div>
    <van-button size="small" type="danger" round @click="$emit('add', p)">+</van-button>
  </div>
</template>

<script setup lang="ts">
import { fmtMoney } from "../../shared/format";
defineProps<{ p: any }>();
defineEmits(["add"]);
</script>
```

（根 `frontend/public/placeholder.png`：放一张 1×1 灰色 PNG 即可，执行时用 base64 解码生成：）

```bash
mkdir -p frontend/public && echo 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==' | base64 -d > frontend/public/placeholder.png
```

- [ ] **Step 4: 实现商品详情** `frontend/src/mobile/views/ProductView.vue` + 路由追加

```vue
<template>
  <div class="p-4" v-if="p">
    <img :src="p.image || '/placeholder.png'" class="w-full rounded-lg bg-gray-100" style="aspect-ratio:1;object-fit:cover" />
    <h3 class="text-xl font-bold mt-3">{{ p.name }}</h3>
    <p class="text-sm text-gray-500 mt-1">规格 {{ p.spec }}｜单位 {{ p.unit }}</p>
    <p class="text-sm text-gray-500" v-if="p.brand || p.origin">
      {{ p.brand }} {{ p.origin }}
    </p>
    <div class="mt-3">
      <span class="text-2xl text-red-500 font-bold">￥{{ fmtMoney(p.price_sale) }}</span>
      <span class="ml-2 text-sm text-gray-400 line-through">
        ￥{{ fmtMoney(p.price_original) }}
      </span>
    </div>
    <van-action-bar>
      <van-action-bar-button type="danger" text="加入购物车" @click="add" />
    </van-action-bar>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { showToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const route = useRoute();
const router = useRouter();
const cart = useCartStore();
const p = ref<any>(null);

function add() {
  cart.add(p.value);
  showToast("已加入购物车");
  router.back();
}

onMounted(async () => {
  try {
    p.value = await api(`/api/products/${route.params.id}`);
  } catch (e: any) {
    showToast(e.message);
    router.replace("/m");
  }
});
</script>
```

路由 children 追加：`{ path: "product/:id", component: () => import("../mobile/views/ProductView.vue") }`；`ProductCard.vue` 的商品名区域包上 `<router-link :to="'/m/product/' + p.id">`（整块可点进详情）。

- [ ] **Step 5: 手动验证 + 构建 + 提交**

后端跑起来（含 seed），dev-login 后访问 /m：分类 tab、搜索、加购 toast、点商品进详情。`npm test && npm run build` 通过。

```bash
git add frontend
git commit -m "feat: H5 首页/商品详情/购物车 store"
```

---

### Task 17: 购物车页与下单确认

**Files:**
- Create: `frontend/src/mobile/views/CartView.vue`、`frontend/src/mobile/views/ConfirmView.vue`
- Modify: `frontend/src/router/index.ts`（追加路由 `/m/cart`、`/m/confirm`）、`frontend/src/mobile/MobileLayout.vue`（购物车角标）

**Interfaces:**
- Consumes: `useCartStore`、`POST /api/orders`
- Produces: 路由 `/m/cart`、`/m/confirm`；下单成功 → `cart.clear()` → 跳 `/m/order/{id}`（Task 18 的详情页，仍为占位时先跳 `/m/orders`）

- [ ] **Step 1: 购物车页** `frontend/src/mobile/views/CartView.vue`

```vue
<template>
  <div class="p-3">
    <h3 class="text-lg font-bold mb-2">购物车</h3>
    <van-empty v-if="!cart.items.length" description="购物车是空的">
      <van-button round type="danger" size="small" @click="$router.push('/m')">
        去逛逛
      </van-button>
    </van-empty>
    <div v-for="i in cart.items" :key="i.product_id"
         class="flex items-center gap-3 p-3 bg-white rounded-lg mb-2">
      <div class="flex-1">
        <div class="font-medium">{{ i.name }}</div>
        <div class="text-xs text-gray-400">{{ i.spec }} / {{ i.unit }}</div>
        <div class="text-red-500">￥{{ fmtMoney(i.price_sale) }}</div>
      </div>
      <van-stepper :model-value="i.qty" min="0" @change="(q: number) => cart.setQty(i.product_id, q)" />
    </div>
    <van-submit-bar v-if="cart.count" :price="cart.totalCents" button-text="去下单"
                    @submit="$router.push('/m/confirm')" />
  </div>
</template>

<script setup lang="ts">
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";
const cart = useCartStore();
</script>
```

- [ ] **Step 2: 下单确认页** `frontend/src/mobile/views/ConfirmView.vue`

```vue
<template>
  <div class="p-3">
    <h3 class="text-lg font-bold mb-2">确认订单</h3>
    <div class="bg-white rounded-lg p-3 mb-3">
      <div v-for="i in cart.items" :key="i.product_id"
           class="flex justify-between py-1 text-sm">
        <span>{{ i.name }}（{{ i.spec }}）× {{ i.qty }}{{ i.unit }}</span>
        <span>￥{{ fmtMoney(i.price_sale * i.qty) }}</span>
      </div>
      <div class="flex justify-between pt-2 mt-1 border-t font-bold">
        <span>合计</span><span class="text-red-500">￥{{ fmtMoney(cart.totalCents) }}</span>
      </div>
    </div>
    <van-field v-model="remark" label="备注" placeholder="选填，如：周五下午取"
               maxlength="100" />
    <div class="p-3 text-xs text-gray-400 leading-5">
      提交后请等待后勤备货，状态变为「待取货」即可到服务点取货，
      取货时出示取货码，现场支付。
    </div>
    <div class="p-3">
      <van-button round block type="danger" :loading="submitting"
                  @click="submit">提交订单</van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { showFailToast, showSuccessToast } from "vant";
import { api } from "../../api/http";
import { useCartStore } from "../../stores/cart";
import { fmtMoney } from "../../shared/format";

const cart = useCartStore();
const router = useRouter();
const remark = ref("");
const submitting = ref(false);

async function submit() {
  submitting.value = true;
  try {
    const order = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({
        items: cart.items.map((i) => ({ product_id: i.product_id, qty: i.qty })),
        remark: remark.value,
      }),
    });
    cart.clear();
    showSuccessToast("下单成功");
    router.replace(`/m/order/${order.id}`);
  } catch (e: any) {
    showFailToast(e.message); // 含"已下架请重新确认/库存不足"等服务端校验文案
    if (e.message.includes("下架") || e.message.includes("库存")) {
      router.replace("/m/cart");
    }
  } finally {
    submitting.value = false;
  }
}
</script>
```

- [ ] **Step 3: 路由与角标**

路由 children 追加两条：`{ path: "cart", ... }`、`{ path: "confirm", ... }`。MobileLayout 的「商品」tab 加角标：

```vue
<van-tabbar-item to="/m" icon="shop-o">商品
  <template #icon>
    <van-badge :content="cart.count || ''">
      <van-icon name="shop-o" />
    </van-badge>
  </template>
</van-tabbar-item>
```

（script 里 `import { useCartStore } from "../../stores/cart"; const cart = useCartStore();`；同时购物车页可通过首页右上角入口进入——MobileLayout 中 HomeView 外层加固定入口，或在 tabbar 保持三项，购物车入口放首页标题栏。简单起见：HomeView 搜索栏右侧加购物车图标按钮跳 `/m/cart`。）

- [ ] **Step 4: 手动验证 + 构建**

dev-login → 加购 2 件 → 购物车改数量 → 下单（填备注）→ 提示成功跳订单页（占位页即可）。再测一次库存不足场景（后台把某商品库存改为 1，前台买 2）→ 报错提示。`npm run build` 通过。

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: H5 购物车与下单确认页"
```

---

### Task 18: 我的订单与取货码展示

**Files:**
- Create: `frontend/src/mobile/components/PickupCode.vue`
- Modify: `frontend/src/mobile/views/OrdersView.vue`（全量替换占位）、`frontend/src/mobile/views/OrderDetailView.vue`（全量替换占位）

**Interfaces:**
- Consumes: `GET /api/orders?status=`、`GET /api/orders/{id}`、`POST /api/orders/{id}/cancel`
- Produces: `PickupCode` 组件（props `{code, orderNo}`，大号数字 + 二维码，二维码内容 `SC:{orderNo}:{code}`）

- [ ] **Step 1: PickupCode 组件**

```bash
cd frontend && npm install qrcode && npm install -D @types/qrcode
```

`frontend/src/mobile/components/PickupCode.vue`:

```vue
<template>
  <div class="flex flex-col items-center p-4 bg-white rounded-lg">
    <div class="text-sm text-gray-500 mb-1">取货码（出示给工作人员）</div>
    <div class="text-4xl font-bold tracking-[0.3em] mb-3">{{ code }}</div>
    <img v-if="dataUrl" :src="dataUrl" class="w-44 h-44" alt="取货二维码" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import QRCode from "qrcode";

const props = defineProps<{ code: string; orderNo: string }>();
const dataUrl = ref("");

onMounted(async () => {
  dataUrl.value = await QRCode.toDataURL(`SC:${props.orderNo}:${props.code}`, {
    width: 320, margin: 1,
  });
});
</script>
```

- [ ] **Step 2: 订单列表页** `frontend/src/mobile/views/OrdersView.vue`

```vue
<template>
  <div class="p-3">
    <van-tabs v-model:active="tab" @change="load">
      <van-tab v-for="(label, s) in TABS" :key="s" :title="label" :name="s" />
    </van-tabs>
    <div v-for="o in orders" :key="o.id"
         class="bg-white rounded-lg p-3 mb-2" @click="$router.push(`/m/order/${o.id}`)">
      <div class="flex justify-between text-sm">
        <span class="text-gray-500">{{ o.order_no }}</span>
        <span :class="o.status === 'DONE' ? 'text-green-600'
                      : o.status === 'CANCELLED' ? 'text-gray-400'
                      : 'text-orange-500'">{{ o.status_label }}</span>
      </div>
      <div class="mt-1 text-sm">{{ itemsText(o) }}</div>
      <div class="flex justify-between items-center mt-1">
        <span class="text-xs text-gray-400">{{ (o.created_at || "").slice(5, 16) }}</span>
        <span class="font-bold">￥{{ fmtMoney(o.total) }}</span>
      </div>
    </div>
    <van-empty v-if="!orders.length" description="暂无订单" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const TABS: Record<string, string> = { "": "全部", PENDING: "待备货", READY: "待取货", DONE: "已完成" };
const tab = ref("");
const orders = ref<any[]>([]);

function itemsText(o: any) {
  return o.items.map((i: any) => `${i.p_name}×${i.qty}`).join("；");
}

function load() {
  const params = tab.value ? `?status=${tab.value}` : "";
  api(`/api/orders${params}`).then((d: any) => (orders.value = d.items));
}

onMounted(load);
</script>
```

- [ ] **Step 3: 订单详情页** `frontend/src/mobile/views/OrderDetailView.vue`

```vue
<template>
  <div class="p-3" v-if="o">
    <PickupCode v-if="o.status === 'READY' || o.status === 'PENDING'"
                :code="o.pickup_code" :order-no="o.order_no" />
    <div class="bg-white rounded-lg p-3 my-3">
      <div class="flex justify-between">
        <span class="font-bold">{{ o.status_label }}</span>
        <span class="text-xs text-gray-400">{{ o.order_no }}</span>
      </div>
      <div class="mt-2 text-sm">
        <div v-for="(i, idx) in o.items" :key="idx" class="flex justify-between py-1">
          <span>{{ i.p_name }}（{{ i.p_spec }}）× {{ i.qty }}{{ i.p_unit }}</span>
          <span>￥{{ fmtMoney(i.subtotal) }}</span>
        </div>
        <div class="flex justify-between pt-2 border-t font-bold">
          <span>合计（取货时支付）</span>
          <span class="text-red-500">￥{{ fmtMoney(o.total) }}</span>
        </div>
        <div class="text-xs text-gray-400 mt-2" v-if="o.remark">备注：{{ o.remark }}</div>
        <div class="text-xs text-red-400 mt-2" v-if="o.status === 'CANCELLED'">
          取消原因：{{ o.cancel_reason }}
        </div>
      </div>
    </div>
    <van-button v-if="o.status === 'PENDING' || o.status === 'READY'" block round
                type="default" @click="cancel">取消订单</van-button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { showConfirmDialog, showFailToast, showSuccessToast } from "vant";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";
import PickupCode from "../components/PickupCode.vue";

const route = useRoute();
const o = ref<any>(null);

async function load() {
  o.value = await api(`/api/orders/${route.params.id}`);
}

async function cancel() {
  await showConfirmDialog({ title: "取消订单", message: "确定取消这个订单吗？" });
  try {
    await api(`/api/orders/${route.params.id}/cancel`, { method: "POST" });
    showSuccessToast("已取消");
    load();
  } catch (e: any) {
    showFailToast(e.message);
  }
}

onMounted(load);
</script>
```

- [ ] **Step 4: 手动验证 + 构建**

完整链路：下单 → 订单列表出现（待备货）→ 详情见取货码大字与二维码 → 取消 → 状态已取消。`npm run build` 通过。

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: H5 我的订单/订单详情/取货码展示"
```

---

### Task 19: 管理端壳与登录页

**Files:**
- Create: `frontend/src/admin/AdminLayout.vue`、`frontend/src/admin/views/{DashboardView,ProductsView,OrdersView,VerifyView,StatsView,SettingsView}.vue`（占位）
- Modify: `frontend/src/admin/views/LoginView.vue`（全量替换占位）、`frontend/src/router/index.ts`（admin 子路由）

**Interfaces:**
- Consumes: `useAdminStore`
- Produces: `/admin` 布局（侧边菜单：工作台/商品管理/订单管理/核销/统计对账/系统设置——最后一项仅 super 可见）、登录页；全部子路由占位页就位

- [ ] **Step 1: 登录页** `frontend/src/admin/views/LoginView.vue`

```vue
<template>
  <div class="h-screen flex items-center justify-center bg-gray-100">
    <el-card class="w-96">
      <h3 class="text-lg font-bold mb-4 text-center">食材预订 · 管理后台</h3>
      <el-form @submit.prevent="login">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" size="large"
                    show-password @keyup.enter="login" />
        </el-form-item>
        <el-button type="primary" size="large" class="w-full" :loading="loading"
                   @click="login">登 录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAdminStore } from "../../stores/admin";

const username = ref("");
const password = ref("");
const loading = ref(false);
const router = useRouter();
const store = useAdminStore();

async function login() {
  if (!username.value || !password.value) return;
  loading.value = true;
  try {
    await store.login(username.value, password.value);
    router.push("/admin/dashboard");
  } catch (e: any) {
    ElMessage.error(e.message); // 含锁定提示文案
  } finally {
    loading.value = false;
  }
}
</script>
```

- [ ] **Step 2: 布局** `frontend/src/admin/AdminLayout.vue`

```vue
<template>
  <el-container class="h-screen">
    <el-aside width="200px" class="border-r">
      <div class="h-14 flex items-center justify-center font-bold border-b">
        食材预订管理
      </div>
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/admin/dashboard">工作台</el-menu-item>
        <el-menu-item index="/admin/products">商品管理</el-menu-item>
        <el-menu-item index="/admin/orders">订单管理</el-menu-item>
        <el-menu-item index="/admin/verify">核销</el-menu-item>
        <el-menu-item index="/admin/stats">统计对账</el-menu-item>
        <el-menu-item v-if="store.admin?.role === 'super'" index="/admin/settings">
          系统设置
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="flex items-center justify-end border-b">
        <span class="mr-3 text-sm text-gray-500">{{ store.admin?.name || store.admin?.username }}</span>
        <el-button link type="danger" @click="logout">退出</el-button>
      </el-header>
      <el-main class="bg-gray-50"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useAdminStore } from "../../stores/admin";

const store = useAdminStore();
const router = useRouter();

async function logout() {
  await store.logout();
  router.push("/admin/login");
}
</script>
```

- [ ] **Step 3: 路由**（router/index.ts 的 admin 段替换为）

```ts
    {
      path: "/admin",
      component: () => import("../admin/AdminLayout.vue"),
      children: [
        { path: "", redirect: "/admin/dashboard" },
        { path: "dashboard", component: () => import("../admin/views/DashboardView.vue") },
        { path: "products", component: () => import("../admin/views/ProductsView.vue") },
        { path: "orders", component: () => import("../admin/views/OrdersView.vue") },
        { path: "verify", component: () => import("../admin/views/VerifyView.vue") },
        { path: "stats", component: () => import("../admin/views/StatsView.vue") },
        { path: "settings", component: () => import("../admin/views/SettingsView.vue") },
      ],
    },
```

六个 views/*.vue 占位（每个都是 `<template><div>建设中</div></template>`）。

- [ ] **Step 4: 手动验证 + 构建**

访问 `/admin` 未登录跳登录页 → seed 初始账号（admin/admin123）登录 → 布局与菜单出现，退出正常。`npm run build` 通过。

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: 管理端布局/登录/路由壳"
```

---

### Task 20: 工作台与统计对账页

**Files:**
- Modify: `frontend/src/admin/views/DashboardView.vue`、`frontend/src/admin/views/StatsView.vue`（替换占位）

**Interfaces:**
- Consumes: `GET /api/admin/stats/dashboard`、`GET /api/admin/stats?date_from=&date_to=`、`GET /api/admin/stats/export?...`

- [ ] **Step 1: 工作台**

```vue
<template>
  <div v-if="d">
    <div class="grid grid-cols-4 gap-4 mb-6">
      <el-card v-for="c in cards" :key="c.label">
        <div class="text-xs text-gray-400">{{ c.label }}</div>
        <div class="text-2xl font-bold mt-1">{{ c.value }}</div>
      </el-card>
    </div>
    <el-card header="近 7 日">
      <div class="flex items-end gap-3 h-40">
        <div v-for="b in d.last7" :key="b.date" class="flex-1 flex flex-col items-center gap-1">
          <div class="w-full bg-orange-300 rounded-t relative flex-1 flex items-end">
            <div class="w-full bg-orange-500 rounded-t"
                 :style="{ height: barHeight(b.orders) }" />
          </div>
          <div class="text-xs text-gray-400">{{ b.date }}</div>
          <div class="text-xs">{{ b.orders }}单 / ￥{{ fmtMoney(b.sales) }}</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const d = ref<any>(null);
const cards = computed(() => d.value ? [
  { label: "今日新增订单", value: d.value.today_new },
  { label: "待备货", value: d.value.pending },
  { label: "待取货", value: d.value.ready },
  { label: "今日核销金额", value: "￥" + fmtMoney(d.value.today_done_amount) },
] : []);

function barHeight(n: number) {
  const max = Math.max(...d.value.last7.map((x: any) => x.orders), 1);
  return `${(n / max) * 100}%`;
}

onMounted(async () => (d.value = await api("/api/admin/stats/dashboard")));
</script>
```

- [ ] **Step 2: 统计对账页**

```vue
<template>
  <div>
    <el-card class="mb-4">
      <div class="flex items-center gap-3">
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                        start-placeholder="开始" end-placeholder="结束" />
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="exportXlsx">导出核销流水</el-button>
      </div>
    </el-card>
    <div class="grid grid-cols-3 gap-4 mb-4" v-if="s">
      <el-card><div class="text-xs text-gray-400">订单总数</div>
        <div class="text-xl font-bold mt-1">{{ s.order_count }}</div></el-card>
      <el-card><div class="text-xs text-gray-400">核销单数</div>
        <div class="text-xl font-bold mt-1">{{ s.done_count }}</div></el-card>
      <el-card><div class="text-xs text-gray-400">核销金额</div>
        <div class="text-xl font-bold mt-1 text-red-500">￥{{ fmtMoney(s.done_amount) }}</div></el-card>
    </div>
    <el-card header="商品销量排行" v-if="s">
      <el-table :data="s.top_products">
        <el-table-column type="index" width="60" />
        <el-table-column prop="name" label="商品" />
        <el-table-column prop="qty" label="数量" width="120" />
        <el-table-column label="金额" width="160">
          <template #default="{ row }">￥{{ fmtMoney(row.amount) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, download } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const today = new Date().toISOString().slice(0, 10);
const range = ref<[string, string]>([today, today]);
const s = ref<any>(null);

function load() {
  const [f, t] = range.value;
  s.value = null;
  api(`/api/admin/stats?date_from=${f}&date_to=${t}`).then((d: any) => (s.value = d));
}

function exportXlsx() {
  const [f, t] = range.value;
  download(`/api/admin/stats/export?date_from=${f}&date_to=${t}`);
}

onMounted(load);
</script>
```

- [ ] **Step 3: 验证 + 构建 + Commit**

造几单数据后核对数字与导出文件。`npm run build` 通过。

```bash
git add frontend
git commit -m "feat: 管理端工作台与统计对账页"
```

---

### Task 21: 商品管理页（CRUD/上传/分类/Excel）

**Files:**
- Modify: `frontend/src/admin/views/ProductsView.vue`（替换占位）

**Interfaces:**
- Consumes: `/api/admin/products*`、`/api/admin/categories*`、`/api/admin/upload`、`/api/admin/products/template|import|export`

- [ ] **Step 1: 实现**（单文件较长的完整实现）

```vue
<template>
  <div>
    <el-card class="mb-4">
      <div class="flex flex-wrap items-center gap-3">
        <el-input v-model="q" placeholder="商品名称" class="w-48" clearable
                  @keyup.enter="load" />
        <el-select v-model="categoryId" placeholder="全部分类" clearable class="w-36"
                   @change="load">
          <el-option v-for="c in cats" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <el-select v-model="status" placeholder="全部状态" clearable class="w-28" @change="load">
          <el-option label="在售" value="on" /><el-option label="下架" value="off" />
        </el-select>
        <el-button @click="load">查询</el-button>
        <div class="flex-1" />
        <el-button @click="download('/api/admin/products/template')">下载导入模板</el-button>
        <el-upload :show-file-list="false" accept=".xlsx" :http-request="doImport">
          <el-button>Excel 导入</el-button>
        </el-upload>
        <el-button @click="download('/api/admin/products/export')">导出</el-button>
        <el-button @click="openCats">分类管理</el-button>
        <el-button type="primary" @click="openEdit()">新增商品</el-button>
      </div>
    </el-card>
    <el-card>
      <el-table :data="items" @selection-change="(s: any[]) => (sel = s)">
        <el-table-column type="selection" width="44" />
        <el-table-column label="图片" width="72">
          <template #default="{ row }">
            <el-image :src="row.image || '/placeholder.png'" fit="cover"
                      style="width:44px;height:44px;border-radius:4px" />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="spec" label="规格" width="90" />
        <el-table-column prop="unit" label="单位" width="64" />
        <el-table-column label="售价" width="100">
          <template #default="{ row }">
            <span class="text-red-500">￥{{ fmtMoney(row.price_sale) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="原价" width="100">
          <template #default="{ row }">{{ fmtMoney(row.price_original) }}</template>
        </el-table-column>
        <el-table-column label="库存" width="90">
          <template #default="{ row }">
            {{ row.stock === null ? "无限" : row.stock }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'on' ? 'success' : 'info'">
              {{ row.status === "on" ? "在售" : "下架" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link :type="row.status === 'on' ? 'info' : 'success'"
                       @click="toggle(row)">
              {{ row.status === "on" ? "下架" : "上架" }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="mt-3" layout="prev, pager, next, total" :total="total"
                     :page-size="20" :current-page="page" @current-change="load" />
    </el-card>

    <el-dialog v-model="editVisible" :title="form.id ? '编辑商品' : '新增商品'" width="560">
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <div class="flex gap-2">
          <el-form-item label="规格"><el-input v-model="form.spec" /></el-form-item>
          <el-form-item label="单位"><el-input v-model="form.unit" style="width:90px" /></el-form-item>
        </div>
        <div class="flex gap-2">
          <el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item>
          <el-form-item label="产地"><el-input v-model="form.origin" /></el-form-item>
        </div>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" clearable placeholder="未分类" class="w-full">
            <el-option v-for="c in cats" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <div class="flex gap-2">
          <el-form-item label="原价(元)"><el-input-number v-model="form._po"
            :min="0" :precision="2" :step="0.1" /></el-form-item>
          <el-form-item label="售价(元)"><el-input-number v-model="form._ps"
            :min="0.01" :precision="2" :step="0.1" /></el-form-item>
        </div>
        <el-form-item label="库存">
          <el-input-number v-model="form._stock" :min="0" placeholder="留空=无限" />
          <span class="ml-2 text-xs text-gray-400">清空数值表示不限库存</span>
        </el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
        <el-form-item label="图片">
          <img v-if="form.image" :src="form.image"
               class="w-16 h-16 rounded mr-2 object-cover" />
          <el-upload :show-file-list="false" accept=".jpg,.jpeg,.png,.webp"
                     :http-request="doUpload">
            <el-button>{{ form.image ? "更换图片" : "上传图片" }}</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="catsVisible" title="分类管理" width="480">
      <el-table :data="cats" size="small">
        <el-table-column label="名称">
          <template #default="{ row }">
            <el-input v-model="row.name" size="small" @change="saveCat(row)" />
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="saveCat(row)" />
          </template>
        </el-table-column>
        <el-table-column label="排序" width="90">
          <template #default="{ row }">
            <el-input-number v-model="row.sort" size="small" controls-position="right"
                             @change="saveCat(row)" />
          </template>
        </el-table-column>
      </el-table>
      <div class="mt-3 flex gap-2">
        <el-input v-model="newCat" placeholder="新分类名称" size="small" />
        <el-button size="small" @click="addCat">添加</el-button>
      </div>
    </el-dialog>

    <el-dialog v-model="importResultVisible" title="导入结果" width="520">
      <p>新增 {{ importResult?.created }} 条，更新 {{ importResult?.updated }} 条。</p>
      <el-alert v-for="e in importResult?.errors || []" :key="e.row" type="error"
                :closable="false" class="mb-1"
                :title="`第 ${e.row} 行：${e.msg}`" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { api, download } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const q = ref(""), categoryId = ref<number | undefined>(), status = ref("");
const cats = ref<any[]>([]), items = ref<any[]>([]), sel = ref<any[]>([]);
const total = ref(0), page = ref(1);
const editVisible = ref(false);
const form = reactive<any>({});
const catsVisible = ref(false), newCat = ref("");
const importResult = ref<any>(null), importResultVisible = ref(false);

async function load(p = 1) {
  page.value = p;
  const params = new URLSearchParams({ page: String(p) });
  if (q.value) params.set("q", q.value);
  if (categoryId.value) params.set("category_id", String(categoryId.value));
  if (status.value) params.set("status", status.value);
  const d = await api(`/api/admin/products?${params}`);
  items.value = d.items;
  total.value = d.total;
}

function openEdit(row?: any) {
  Object.assign(form, row || {
    id: 0, name: "", spec: "", unit: "件", brand: "", origin: "",
    category_id: null, sort: 0, image: null,
    _po: 0, _ps: 0, _stock: null,
  });
  if (row) {
    form._po = row.price_original / 100;
    form._ps = row.price_sale / 100;
    form._stock = row.stock;
  }
  editVisible.value = true;
}

async function save() {
  const body = {
    name: form.name, spec: form.spec, unit: form.unit || "件",
    brand: form.brand || "", origin: form.origin || "",
    category_id: form.category_id || null,
    price_original: Math.round((form._po || 0) * 100),
    price_sale: Math.round((form._ps || 0) * 100),
    stock: form._stock ?? null, sort: form.sort || 0,
    status: form.status || "on", image: form.image || null,
  };
  try {
    if (form.id) await api(`/api/admin/products/${form.id}`, {
      method: "PUT", body: JSON.stringify(body) });
    else await api("/api/admin/products", {
      method: "POST", body: JSON.stringify(body) });
    ElMessage.success("已保存");
    editVisible.value = false;
    load(page.value);
  } catch (e: any) { ElMessage.error(e.message); }
}

async function toggle(row: any) {
  await api(`/api/admin/products/${row.id}`, {
    method: "PUT",
    body: JSON.stringify({ ...row, status: row.status === "on" ? "off" : "on",
                           stock: row.stock }),
  });
  load(page.value);
}

async function doUpload(opt: any) {
  const fd = new FormData();
  fd.append("file", opt.file);
  try {
    const d = await api("/api/admin/upload", { method: "POST", body: fd });
    form.image = d.url;
    ElMessage.success("图片已上传");
  } catch (e: any) { ElMessage.error(e.message); }
}

async function doImport(opt: any) {
  const fd = new FormData();
  fd.append("file", opt.file);
  try {
    importResult.value = await api("/api/admin/products/import", {
      method: "POST", body: fd });
    importResultVisible.value = true;
    load(1);
  } catch (e: any) { ElMessage.error(e.message); }
}

async function loadCats() {
  cats.value = await api("/api/admin/categories");
}

async function saveCat(row: any) {
  await api(`/api/admin/categories/${row.id}`, {
    method: "PUT",
    body: JSON.stringify({ name: row.name, sort: row.sort || 0,
                           enabled: row.enabled !== false }) });
  loadCats();
  load(page.value);
}

async function addCat() {
  if (!newCat.value) return;
  try {
    await api("/api/admin/categories", {
      method: "POST",
      body: JSON.stringify({ name: newCat.value }) });
    newCat.value = "";
    loadCats();
  } catch (e: any) { ElMessage.error(e.message); }
}

function openCats() { catsVisible.value = true; }

onMounted(() => { loadCats(); load(1); });
</script>
```

（注意：`doUpload/doImport` 用 FormData 时 http.ts 会带 JSON Content-Type 头，需调整 `api()`：当 `opts.body instanceof FormData` 时不设 Content-Type，让浏览器自动带 boundary——Task 3 的 http.ts 修改一行：`headers: opts.body instanceof FormData ? {} : {...}`。）

- [ ] **Step 2: http.ts FormData 兼容**（同上注）

`frontend/src/api/http.ts` 中 headers 行改为：

```ts
const headers: Record<string, string> = opts.body instanceof FormData
  ? {}
  : { "Content-Type": "application/json", ...(opts.headers as any || {}) };
```

- [ ] **Step 3: 验证 + 构建 + Commit**

验证：新增/编辑/上下架/图片上传/模板下载/导入（造一个带错误行的文件看报告）/导出。`npm run build` 通过。

```bash
git add frontend
git commit -m "feat: 管理端商品管理页（CRUD/上传/分类/Excel 导入导出）"
```

---

### Task 22: 订单管理页

**Files:**
- Modify: `frontend/src/admin/views/OrdersView.vue`（替换占位）

**Interfaces:**
- Consumes: `/api/admin/orders*`（检索/ready/cancel/picking-list.xlsx）

- [ ] **Step 1: 实现**

```vue
<template>
  <div>
    <el-card class="mb-4">
      <div class="flex flex-wrap items-center gap-3">
        <el-select v-model="status" placeholder="全部状态" clearable class="w-32" @change="load">
          <el-option label="待备货" value="PENDING" />
          <el-option label="待取货" value="READY" />
          <el-option label="已完成" value="DONE" />
          <el-option label="已取消" value="CANCELLED" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                        start-placeholder="开始" end-placeholder="结束" />
        <el-input v-model="q" placeholder="订单号/取货码/工号/姓名" class="w-52" clearable
                  @keyup.enter="load" />
        <el-button @click="load">查询</el-button>
        <div class="flex-1" />
        <el-button @click="download('/api/admin/orders/picking-list.xlsx')">
          导出备货清单
        </el-button>
        <el-button type="primary" :disabled="!sel.length" @click="batchReady">
          批量备货完成（{{ sel.length }}）
        </el-button>
      </div>
    </el-card>
    <el-card>
      <el-table :data="items" @selection-change="(s: any[]) => (sel = s)">
        <el-table-column type="selection" width="44" :selectable="
          (row: any) => row.status === 'PENDING'" />
        <el-table-column prop="order_no" label="订单号" width="150" />
        <el-table-column label="教职工" width="130">
          <template #default="{ row }">
            {{ row.user?.name || "-" }}（{{ row.user?.empid }}）
          </template>
        </el-table-column>
        <el-table-column prop="pickup_code" label="取货码" width="80" />
        <el-table-column label="商品" min-width="220">
          <template #default="{ row }">
            {{ row.items.map((i: any) => `${i.p_name}×${i.qty}`).join("；") }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="100">
          <template #default="{ row }">￥{{ fmtMoney(row.total) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="TAG[row.status]">{{ row.status_label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下单时间" width="140">
          <template #default="{ row }">{{ (row.created_at || "").slice(0, 16).replace("T", " ") }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'PENDING' || row.status === 'READY'"
                       link type="danger" @click="cancel(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="mt-3" layout="prev, pager, next, total" :total="total"
                     :page-size="20" :current-page="page" @current-change="load" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api, download } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const TAG: Record<string, string> = {
  PENDING: "warning", READY: "success", DONE: "info", CANCELLED: "danger",
};
const status = ref(""), q = ref(""), range = ref<[string, string] | null>(null);
const items = ref<any[]>([]), sel = ref<any[]>([]);
const total = ref(0), page = ref(1);

async function load(p = 1) {
  page.value = p;
  const params = new URLSearchParams({ page: String(p) });
  if (status.value) params.set("status", status.value);
  if (q.value) params.set("q", q.value);
  if (range.value?.[0]) {
    params.set("date_from", range.value[0]);
    params.set("date_to", range.value[1]);
  }
  const d = await api(`/api/admin/orders?${params}`);
  items.value = d.items;
  total.value = d.total;
}

async function batchReady() {
  const r = await api("/api/admin/orders/ready", {
    method: "POST",
    body: JSON.stringify({ ids: sel.value.map((o) => o.id) }),
  });
  ElMessage.success(`备货完成 ${r.updated} 单` + (r.failed.length ? `，失败 ${r.failed.length} 单` : ""));
  load(page.value);
}

async function cancel(row: any) {
  const { value } = await ElMessageBox.prompt("取消原因（必填）", "代取消订单", {
    inputValidator: (v: string) => !!v?.trim() || "请填写原因",
  });
  try {
    await api(`/api/admin/orders/${row.id}/cancel`, {
      method: "POST", body: JSON.stringify({ reason: value }) });
    ElMessage.success("已取消");
    load(page.value);
  } catch (e: any) { ElMessage.error(e.message); }
}

onMounted(() => load(1));
</script>
```

- [ ] **Step 2: 验证 + 构建 + Commit**

验证：筛选/搜索/批量备货/代取消/备货清单导出。`npm run build` 通过。

```bash
git add frontend
git commit -m "feat: 管理端订单管理页（检索/批量备货/代取消）"
```

---

### Task 23: 核销页

**Files:**
- Modify: `frontend/src/admin/views/VerifyView.vue`（替换占位）

**Interfaces:**
- Consumes: `GET/POST /api/admin/verify/{raw}`

- [ ] **Step 1: 实现**

```vue
<template>
  <div class="max-w-xl mx-auto">
    <el-card>
      <div class="text-sm text-gray-400 mb-2">
        光标定位输入框后，用扫码枪扫老师的取货二维码，或手动输入 6 位取货码后回车
      </div>
      <el-input ref="inputRef" v-model="code" size="large" placeholder="扫码 / 输入取货码"
                @keyup.enter="lookup">
        <template #prepend>取货码</template>
      </el-input>
    </el-card>

    <el-dialog v-model="orderVisible" width="460" @closed="resetInput">
      <div v-if="order" class="text-base leading-8">
        <div class="flex justify-between">
          <span class="text-gray-500">订单号</span><span>{{ order.order_no }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">教职工</span>
          <span>{{ order.user?.name || "-" }}（{{ order.user?.empid }}）</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">状态</span>
          <el-tag :type="order.status === 'READY' ? 'success' : 'danger'">
            {{ order.status_label }}
          </el-tag>
        </div>
        <el-divider class="my-2" />
        <div v-for="(i, idx) in order.items" :key="idx" class="flex justify-between">
          <span>{{ i.p_name }}（{{ i.p_spec }}）× {{ i.qty }}{{ i.p_unit }}</span>
          <span>￥{{ fmtMoney(i.subtotal) }}</span>
        </div>
        <el-divider class="my-2" />
        <div class="flex justify-between items-center">
          <span class="font-bold">应收金额（现场收取）</span>
          <span class="text-2xl font-bold text-red-500">￥{{ fmtMoney(order.total) }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="orderVisible = false">关闭</el-button>
        <el-button type="primary" size="large" :disabled="!order?.verifiable"
                   @click="confirm">确认核销</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { api } from "../../api/http";
import { fmtMoney } from "../../shared/format";

const code = ref("");
const inputRef = ref();
const order = ref<any>(null);
const orderVisible = ref(false);

function resetInput() {
  code.value = "";
  nextTick(() => inputRef.value?.focus());
}

async function lookup() {
  if (!code.value.trim()) return;
  try {
    const d = await api(`/api/admin/verify/${encodeURIComponent(code.value.trim())}`);
    order.value = d.order;
    orderVisible.value = true;
    if (!d.order.verifiable) {
      ElMessage.warning(`当前状态「${d.order.status_label}」不可核销` +
        (d.order.status === "PENDING" ? "，请先在订单管理做备货完成" : ""));
    }
  } catch (e: any) {
    ElMessage.error(e.message); // 红字：码不存在/状态拦截
    resetInput();
  }
}

async function confirm() {
  try {
    await api(`/api/admin/verify/${encodeURIComponent(order.value.pickup_code)}`,
              { method: "POST" });
    ElMessage.success(`核销成功，应收 ￥${fmtMoney(order.value.total)}`);
    orderVisible.value = false;
  } catch (e: any) {
    ElMessage.error(e.message);
    orderVisible.value = false;
  }
}

onMounted(resetInput);
</script>
```

- [ ] **Step 2: 验证 + 构建 + Commit**

验证：用 H5 下单 → 后台备货完成 → 核销页输码回车 → 弹明细与应收 → 确认成功；重复输同码 → 红字拦截；输 PENDING 单的码 → 提示先备货。`npm run build` 通过。

```bash
git add frontend
git commit -m "feat: 管理端核销页（扫码/输码、金额确认、状态拦截）"
```

---

### Task 24: 系统设置页（账号/须知/日志）

**Files:**
- Modify: `frontend/src/admin/views/SettingsView.vue`（替换占位）

**Interfaces:**
- Consumes: `/api/admin/admins*`、`/api/admin/settings/notice`、`/api/admin/logs`

- [ ] **Step 1: 实现**

```vue
<template>
  <el-card>
    <el-tabs v-model="tab">
      <el-tab-pane label="管理员账号" name="admins">
        <el-button type="primary" class="mb-3" @click="openEdit()">新增账号</el-button>
        <el-table :data="admins">
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              <el-tag :type="row.role === 'super' ? 'danger' : 'info'">
                {{ row.role === "super" ? "超级管理员" : "操作员" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? "启用" : "停用" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近登录" width="160">
            <template #default="{ row }">
              {{ (row.last_login_at || "-").slice(0, 16).replace("T", " ") }}
            </template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="{ row }">
              <el-button link @click="openEdit(row)">编辑</el-button>
              <el-button link type="warning" @click="resetPwd(row)">重置密码</el-button>
              <el-button link :type="row.is_active ? 'danger' : 'success'" @click="toggle(row)">
                {{ row.is_active ? "停用" : "启用" }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="取货须知" name="notice">
        <el-input v-model="notice" type="textarea" :rows="8" maxlength="500" show-word-limit
                  placeholder="服务点位置、营业时间、支付方式说明…" />
        <el-button type="primary" class="mt-3" @click="saveNotice">保存</el-button>
      </el-tab-pane>

      <el-tab-pane label="操作日志" name="logs">
        <el-table :data="logs">
          <el-table-column prop="created_at" label="时间" width="160">
            <template #default="{ row }">
              {{ (row.created_at || "").slice(0, 19).replace("T", " ") }}
            </template>
          </el-table-column>
          <el-table-column prop="username" label="账号" width="120" />
          <el-table-column prop="action" label="动作" width="120" />
          <el-table-column prop="target" label="对象" width="160" />
          <el-table-column prop="detail" label="详情" />
        </el-table>
        <el-pagination class="mt-3" layout="prev, pager, next, total" :total="logTotal"
                       :page-size="20" @current-change="loadLogs" />
      </el-tab-pane>
    </el-tabs>
  </el-card>

  <el-dialog v-model="editVisible" :title="form.id ? '编辑账号' : '新增账号'" width="420">
    <el-form label-width="80px">
      <el-form-item label="用户名"><el-input v-model="form.username" :disabled="!!form.id" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option label="操作员" value="operator" />
          <el-option label="超级管理员" value="super" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="!form.id" label="初始密码">
        <el-input v-model="form.password" type="password" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { api } from "../../api/http";

const tab = ref("admins");
const admins = ref<any[]>([]);
const notice = ref("");
const logs = ref<any[]>([]);
const logTotal = ref(0);
const editVisible = ref(false);
const form = reactive<any>({});

async function loadAdmins() { admins.value = await api("/api/admin/admins"); }
async function loadLogs(p = 1) {
  const d = await api(`/api/admin/logs?page=${p}`);
  logs.value = d.items;
  logTotal.value = d.total;
}

function openEdit(row?: any) {
  Object.assign(form, row || { id: 0, username: "", name: "", role: "operator", password: "" });
  editVisible.value = true;
}

async function save() {
  try {
    if (form.id) {
      await api(`/api/admin/admins/${form.id}`, {
        method: "PUT",
        body: JSON.stringify({ role: form.role, name: form.name }) });
    } else {
      await api("/api/admin/admins", { method: "POST", body: JSON.stringify(form) });
    }
    ElMessage.success("已保存");
    editVisible.value = false;
    loadAdmins();
  } catch (e: any) { ElMessage.error(e.message); }
}

async function resetPwd(row: any) {
  const { value } = await ElMessageBox.prompt("输入新密码（至少 6 位）", "重置密码");
  try {
    await api(`/api/admin/admins/${row.id}`, {
      method: "PUT", body: JSON.stringify({ password: value }) });
    ElMessage.success("已重置");
  } catch (e: any) { ElMessage.error(e.message); }
}

async function toggle(row: any) {
  await api(`/api/admin/admins/${row.id}`, {
    method: "PUT", body: JSON.stringify({ is_active: !row.is_active }) });
  loadAdmins();
}

async function loadNotice() {
  const d = await api("/api/admin/settings/notice");
  notice.value = d.content;
}

async function saveNotice() {
  await api("/api/admin/settings/notice", {
    method: "PUT", body: JSON.stringify({ content: notice.value }) });
  ElMessage.success("已保存，教职工端即时生效");
}

onMounted(() => { loadAdmins(); loadNotice(); loadLogs(1); });
</script>
```

- [ ] **Step 2: 验证 + 构建 + Commit**

验证：新增操作员→其登录无"系统设置"菜单；重置密码/停用生效；须知保存后 H5 端可见；日志列表有核销/登录记录。`npm run build` 通过。

```bash
git add frontend
git commit -m "feat: 管理端系统设置页（账号/须知/日志）"
```

---

### Task 25: E2E 主链路与覆盖率检查

**Files:**
- Create: `e2e/package.json`、`e2e/playwright.config.ts`、`e2e/tests/main-flow.spec.ts`、`e2e/tests/cancel-flow.spec.ts`、`scripts/e2e-up.sh`

**Interfaces:**
- Consumes: 已完成的全部前后端（dev-login 旁路 + SQLite + seed 66 SKU）

- [ ] **Step 1: 起服务脚本** `scripts/e2e-up.sh`

```bash
#!/usr/bin/env bash
# E2E 环境：构建前端 → FastAPI 托管静态文件 + SQLite + dev-login
set -e
cd "$(dirname "$0")/.."
cd frontend && npm run build && cd ..
cd backend
rm -f e2e.db
export DATABASE_URL="sqlite:///./e2e.db"
export DEV_AUTH_ENABLED=1
export UPLOAD_DIR="../uploads"
. .venv/bin/activate
python seed.py
nohup uvicorn app.main:app --host 127.0.0.1 --port 13000 > /tmp/e2e-uvicorn.log 2>&1 &
echo $! > /tmp/e2e-uvicorn.pid
sleep 2
curl -sf http://127.0.0.1:13000/api/health > /dev/null && echo "backend ready"
```

（配套 `scripts/e2e-down.sh`：`kill $(cat /tmp/e2e-uvicorn.pid)`。）

同时 `backend/app/main.py` 需要托管理前端静态产物（SPA 回退），追加在 `create_app()` 末尾：

```python
    import os
    from fastapi.staticfiles import StaticFiles
    dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.isdir(dist):
        app.mount("/", StaticFiles(directory=dist, html=True), name="spa")
```

（mount 在所有路由之后，API 优先匹配；`/m`、`/admin` 等前端路径靠 `html=True` 回退 index.html。注意：`app.mount("/uploads", ...)` 必须在此 mount 之前注册——现有代码已满足。）

- [ ] **Step 2: Playwright 配置与测试**

`e2e/package.json`:

```json
{
  "name": "shicai-e2e",
  "private": true,
  "devDependencies": { "@playwright/test": "^1.44.0" }
}
```

`e2e/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://127.0.0.1:13000" },
  retries: 0,
});
```

`e2e/tests/main-flow.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("主链路：登录→下单→备货→核销", async ({ page }) => {
  // 教职工登录（dev 旁路）并下单
  await page.goto("/api/auth/dev-login?empid=E001&name=王老师");
  await page.goto("/m");
  await page.getByPlaceholder("搜索食材").fill("五常大米");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "+" }).first().click();
  await page.goto("/m/confirm");
  await page.getByPlaceholder("选填，如：周五下午取").fill("E2E 备注");
  await page.getByRole("button", { name: "提交订单" }).click();
  await expect(page.getByText("取货码", { exact: false }).first()).toBeVisible();

  // 管理员备货
  const code = (await page.locator(".tracking-\\[0\\.3em\\]").first().innerText()).trim();
  const admin = await page.context().browser()!.newPage();
  await admin.goto("/admin/login");
  await admin.getByPlaceholder("用户名").fill("admin");
  await admin.getByPlaceholder("密码").fill("admin123");
  await admin.getByRole("button", { name: "登 录" }).click();
  await admin.goto("/admin/orders");
  await admin.getByPlaceholder("订单号/取货码/工号/姓名").fill(code);
  await admin.keyboard.press("Enter");
  await admin.locator("el-table").getByRole("checkbox").first().check();
  await admin.getByRole("button", { name: /批量备货完成/ }).click();

  // 核销
  await admin.goto("/admin/verify");
  await admin.getByPlaceholder("扫码 / 输入取货码").fill(code);
  await admin.keyboard.press("Enter");
  await expect(admin.getByText("应收金额", { exact: false })).toBeVisible();
  await admin.getByRole("button", { name: "确认核销" }).click();
  await expect(admin.getByText("核销成功", { exact: false })).toBeVisible();

  // 教职工端看到已完成
  await page.goto("/m/orders");
  await page.getByRole("tab", { name: "已完成" }).click();
  await expect(page.getByText("已完成").first()).toBeVisible();
  await admin.close();
});
```

`e2e/tests/cancel-flow.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("取消链路：下单→用户取消→状态已取消", async ({ page }) => {
  await page.goto("/api/auth/dev-login?empid=E002&name=李老师");
  await page.goto("/m");
  await page.getByRole("button", { name: "+" }).first().click();
  await page.goto("/m/confirm");
  await page.getByRole("button", { name: "提交订单" }).click();
  await page.getByRole("button", { name: "取消订单" }).click();
  await page.getByRole("button", { name: "确定" }).click();
  await expect(page.getByText("已取消").first()).toBeVisible();
});
```

- [ ] **Step 3: 运行**

```bash
cd e2e && npm install && npx playwright install chromium
bash ../scripts/e2e-up.sh && npx playwright test; bash ../scripts/e2e-down.sh
```

Expected: 2 passed（选择器若因组件渲染差异失稳，允许执行者微调选择器但不得删除断言语义）

- [ ] **Step 4: 后端覆盖率**

Run: `cd backend && pytest --cov=app --cov-report=term`
Expected: ≥80%，不足则给核心模块（services、routers）补测试后重跑

- [ ] **Step 5: Commit**

```bash
git add e2e scripts backend/app/main.py
git commit -m "test: E2E 主链路与取消链路，静态托管"
```

---

### Task 26: 部署物（Docker/nginx/备份/README）

**Files:**
- Create: `backend/Dockerfile`、`docker-compose.dev.yml`、`docker-compose.yml`、`nginx/nginx.conf`、`scripts/backup.sh`、`README.md`

**Interfaces:**
- Consumes: 全部
- Produces: 一键开发库（dev compose）、一键生产栈（app+mysql+nginx）、每日备份脚本、部署文档

- [ ] **Step 1: 文件内容**

`backend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS front
WORKDIR /build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /srv
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=front /build/dist ./static
ENV STATIC_DIR=/srv/static UPLOAD_DIR=/srv/uploads
EXPOSE 13000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13000"]
```

（配合 main.py 静态托管目录可配：`dist = os.environ.get("STATIC_DIR", <默认相对路径>)`。）

`docker-compose.dev.yml`（本机开发只起 MySQL）:

```yaml
services:
  mysql:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: shicai
      MYSQL_USER: sc
      MYSQL_PASSWORD: scpass
    ports: ["3306:3306"]
    volumes: ["mysql-data:/var/lib/mysql"]
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
volumes:
  mysql-data:
```

`docker-compose.yml`（生产，构建上下文为仓库根）:

```yaml
services:
  app:
    build:
      context: .
      dockerfile: backend/Dockerfile
    environment:
      DATABASE_URL: mysql+pymysql://sc:scpass@mysql:3306/shicai?charset=utf8mb4
      APP_BASE_URL: ${APP_BASE_URL}
      SESSION_SECRET: ${SESSION_SECRET}
      CAS_BASE_URL: ${CAS_BASE_URL}
      DEV_AUTH_ENABLED: "0"
      INITIAL_ADMIN_USERNAME: ${INITIAL_ADMIN_USERNAME:-admin}
      INITIAL_ADMIN_PASSWORD: ${INITIAL_ADMIN_PASSWORD}
    volumes: ["uploads:/srv/uploads"]
    depends_on: [mysql]
    restart: unless-stopped
  mysql:
    image: mysql:8
    environment:
      MYSQL_DATABASE: shicai
      MYSQL_USER: sc
      MYSQL_PASSWORD: scpass
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    volumes: ["mysql-data:/var/lib/mysql"]
    restart: unless-stopped
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on: [app]
    restart: unless-stopped
volumes:
  mysql-data:
  uploads:
```

`nginx/nginx.conf`（正式域名替换 `shicai.example.edu.cn`）:

```nginx
server {
    listen 80;
    server_name shicai.example.edu.cn;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    http2 on;
    server_name shicai.example.edu.cn;

    ssl_certificate     /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;

    client_max_body_size 10m;

    location / {
        proxy_pass http://app:13000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`scripts/backup.sh`（crontab 每日 2:00）:

```bash
#!/usr/bin/env bash
# 每日备份 MySQL 与上传图片，保留 7 天
set -e
cd "$(dirname "$0")/.."
STAMP=$(date +%F)
docker compose exec -T mysql mysqldump -usc -pscpass shicai | gzip > "backups/db-${STAMP}.sql.gz"
docker compose run --rm -v "$(pwd)/backups:/bk" app tar czf "/bk/uploads-${STAMP}.tgz" /srv/uploads
find backups -mtime +7 -delete
```

`README.md`:

````markdown
# 食材服务点线上预订系统

教职工（企微 H5，CAS 登录）线上预订食材；后勤处（PC 后台，账号密码）管理商品、
备货、核销、对账。取货现场支付，系统不动资金。

## 本地开发

```bash
docker compose -f docker-compose.dev.yml up -d   # MySQL
cd backend && python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                             # 按需修改
python seed.py                                   # 建表+66 SKU+初始管理员
uvicorn app.main:app --host 0.0.0.0 --port 13000
cd ../frontend && npm install && npm run dev     # 5173，代理到 13000
```

本地联调登录：`/api/auth/dev-login?empid=T001&name=张老师`（`DEV_AUTH_ENABLED=1` 时）。

## CAS 联调

1. `CAS_BASE_URL` 填学校 CAS 地址（含 `/cas` 路径）
2. `APP_BASE_URL` 填已报备回调地址（开发期 `http://10.204.0.146:13000`）
3. 验证 `serviceValidate` 是否带姓名属性；不带则用后台「工号-姓名名单导入」或首登补填

## 生产部署

1. 校内服务器装 Docker；正式域名解析到服务器，证书放 `nginx/certs/`
2. **正式域名先到 CAS 管理员处报备 service 回调地址**
3. 根目录 `.env` 配好 `APP_BASE_URL/SESSION_SECRET/CAS_BASE_URL/INITIAL_ADMIN_PASSWORD/ MYSQL_ROOT_PASSWORD`
4. `docker compose up -d --build`
5. 首次进入后台改初始密码；建操作员账号
6. crontab: `0 2 * * * bash /path/to/scripts/backup.sh`

## 备份恢复

`backups/db-*.sql.gz`（数据库）、`backups/uploads-*.tgz`（图片），保留 7 天。
````

- [ ] **Step 2: 验证**

```bash
docker compose -f docker-compose.dev.yml up -d
cd backend && DATABASE_URL=mysql+pymysql://sc:scpass@127.0.0.1:3306/shicai?charset=utf8mb4 python seed.py
docker compose -f docker-compose.yml config   # 生产配置语法检查
```

Expected: MySQL 里 66 条商品；compose 配置无报错

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile docker-compose.dev.yml docker-compose.yml nginx scripts README.md
git commit -m "chore: Docker/nginx 部署物、备份脚本与 README"
```

---

## 计划自审记录

1. **Spec 覆盖**：spec §4 认证→Task 4/5；§5 数据模型→Task 2；§6 教职工端→Task 6/7/8/15-18；§7 管理端→Task 9-14/19-24；§8 边界→各任务测试（见 Review Focus 落点）；§9 安全→Task 5（bcrypt/锁定）、Task 9（上传校验）、全局约束（cookie/参数化）；§10 测试→各任务 pytest + Task 25 E2E/覆盖率；§11 部署→Task 26。姓名三层策略中的「名单导入」未单列任务——由 Task 10 的 Excel 通道 + Task 14 须知之外补充：**执行 Task 10 时在导入模板说明里注明可用于工号-姓名对照表之外的用途即可，教师姓名匹配本期用「CAS 属性 + 首登补填」两层**，二期如需名单导入再加。
2. **占位扫描**：Task 13 曾留错误占位循环，已修正为直接实现；全部步骤均含实码。
3. **类型一致性**：`order_to_dict`、`product_to_dict`、`useCartStore`、`api()`、`STATUS_LABEL` 在生产与消费任务间签名一致；`fmtMoney(cents)` 全前端统一。
4. **Review Focus**：五项均有对应任务测试钉住（Task 5/7/8/12）。

## 执行建议

任务间接口耦合集中在 Task 2（模型）、Task 3（api 封装）、Task 4/5（会话依赖）——建议同一个人（或同一会话）连续执行；Task 15 之后的前端页面任务相互独立，可并行。

