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
