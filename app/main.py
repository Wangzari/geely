"""FastAPI 应用入口：中间件、安全头、路由装配。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .routes import router
from .upstream import UpstreamBusinessError

settings = get_settings()

app = FastAPI(
    title="车辆视频与定位服务",
    version="1.0.0",
    description="对外提供开启多路视频与实时车辆位置的能力。",
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)


@app.exception_handler(UpstreamBusinessError)
async def _upstream_business_error(request: Request, exc: UpstreamBusinessError) -> JSONResponse:
    """上游业务失败（如“车辆不在线”）→ 409 + 真实原因，而非笼统的 502。"""
    return JSONResponse(status_code=409, content={"detail": exc.msg})

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router)
