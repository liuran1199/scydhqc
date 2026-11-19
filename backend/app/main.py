import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.exceptions import AppError

logging.basicConfig(  # 应用日志进 uvicorn 输出（/tmp/prod-uvicorn.log），带时间戳
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(title="食材预订")
    # 不加 CORS：前端由本服务同源托管（SPA 静态 + API），开发走 vite 代理也是同源。
    # 通配 origins + credentials 会放行任意站点带 cookie 跨域请求，宁可不要。

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse({"detail": exc.msg, "code": exc.code}, status_code=exc.status)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    from app.routers.auth import router as auth_router
    app.include_router(auth_router)

    from app.routers.products import router as products_router
    app.include_router(products_router)

    from app.routers.orders import router as orders_router
    app.include_router(orders_router)

    from app.routers.admin_products import router as admin_products_router
    app.include_router(admin_products_router)

    from app.routers.admin_excel import router as admin_excel_router
    app.include_router(admin_excel_router)

    from app.routers.admin_orders import router as admin_orders_router
    app.include_router(admin_orders_router)

    from app.routers.admin_stats import router as admin_stats_router
    app.include_router(admin_stats_router)

    from app.routers.admin_settings import router as admin_settings_router
    from app.routers.public import router as public_router
    app.include_router(admin_settings_router)
    app.include_router(public_router)

    os.makedirs(settings.upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    from app.routers.admin_auth import router as admin_auth_router, ensure_initial_admin
    app.include_router(admin_auth_router)

    # SPA 静态托管：前端构建产物存在时挂到根路径（API 路由已注册在前，优先匹配）
    class SPAStaticFiles(StaticFiles):
        """未命中的非 API/上传路径回退 index.html，保证 /m、/admin 深链可直接访问"""

        async def get_response(self, path: str, scope):
            try:
                return await super().get_response(path, scope)
            except StarletteHTTPException as e:  # StaticFiles 抛的是 starlette 基类
                if e.status_code == 404 and not path.startswith(("api", "uploads")):
                    return await super().get_response("index.html", scope)
                raise

    dist = os.environ.get("STATIC_DIR") or os.path.join(
        os.path.dirname(__file__), "..", "..", "frontend", "dist"
    )
    if os.path.isdir(dist):
        app.mount("/", SPAStaticFiles(directory=dist, html=True), name="spa")

    @app.on_event("startup")
    def on_startup():
        from app.config import validate_security_settings
        validate_security_settings(settings)
        import app.models  # noqa: F401 确保模型注册
        Base.metadata.create_all(bind=engine)
        _ensure_product_images_column()
        _ensure_order_pickup_date_column()
        _ensure_admin_session_version_column()
        with SessionLocal() as s:
            ensure_initial_admin(s)


    def _ensure_product_images_column():
        """已有库升级：products 补 images 列；旧单图数据回填为图集（幂等）"""
        from sqlalchemy import text
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE products ADD COLUMN images TEXT"))
            except Exception:  # 列已存在（MySQL/SQLite 均会报错而非 if not exists）
                pass
            conn.execute(text(
                "UPDATE products SET images = CONCAT('[\"', image, '\"]') "
                "WHERE image IS NOT NULL AND image != '' "
                "AND (images IS NULL OR images = '')"
            ))

    def _ensure_order_pickup_date_column():
        """已有库升级：orders 补 pickup_date 列，历史订单按 16 点截单规则回填（幂等）。

        日期回填在 Python 侧算：MySQL/SQLite 的 SQL 日期函数不统一。
        """
        from datetime import datetime as _dt
        from sqlalchemy import text
        from app.services.orders import pickup_date_for
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE orders ADD COLUMN pickup_date DATE"))
            except Exception:  # 列已存在
                pass
        with SessionLocal() as s:
            rows = s.execute(
                text("SELECT id, created_at FROM orders WHERE pickup_date IS NULL")
            ).all()
            for oid, created in rows:
                placed = created if isinstance(created, _dt) else _dt.fromisoformat(str(created))
                s.execute(text("UPDATE orders SET pickup_date = :d WHERE id = :id"),
                          {"d": pickup_date_for(placed), "id": oid})
            s.commit()

    def _ensure_admin_session_version_column():
        """已有库升级：admins 补 session_version 列（改密撤销旧会话用，幂等）。"""
        from sqlalchemy import text
        with engine.begin() as conn:
            try:
                conn.execute(text(
                    "ALTER TABLE admins ADD COLUMN session_version INT NOT NULL DEFAULT 0"))
            except Exception:  # 列已存在
                pass

    return app


app = create_app()
