import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
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

    from app.routers.products import router as products_router
    app.include_router(products_router)

    from app.routers.orders import router as orders_router
    app.include_router(orders_router)

    from app.routers.admin_products import router as admin_products_router
    app.include_router(admin_products_router)

    from app.routers.admin_excel import router as admin_excel_router
    app.include_router(admin_excel_router)

    os.makedirs(settings.upload_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    from app.routers.admin_auth import router as admin_auth_router, ensure_initial_admin
    app.include_router(admin_auth_router)

    @app.on_event("startup")
    def on_startup():
        import app.models  # noqa: F401 确保模型注册
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as s:
            ensure_initial_admin(s)

    return app


app = create_app()
