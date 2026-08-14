from __future__ import annotations

if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi

from app.api.routes.audit import router as audit_router
from app.api.routes.demo import router as demo_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.health import router as health_router
from app.api.routes.google_crawler import router as google_crawler_router
from app.api.routes.report import router as report_router
from app.api.routes.tasks import router as task_router
from app.api.routes.token_admin import router as token_admin_router
from app.api.token_audit import ApiTokenAuditMiddleware
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.models.responses import error_response

# 初始化结构化日志
configure_logging()
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例，默认使用高性能的 ORJSONResponse 响应格式
app = FastAPI(
    title="GEO Audit Service",
    version="1.0.0",
    debug=settings.debug,
    default_response_class=ORJSONResponse,
)
app.add_middleware(ApiTokenAuditMiddleware)


def custom_openapi() -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["ApiToken"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Token",
        "description": "API access token managed at /token-admin. Legacy X-Demo-Token and Bearer tokens are also accepted.",
    }
    for path, operations in schema.get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            continue
        for operation in operations.values():
            if isinstance(operation, dict):
                operation["security"] = [{"ApiToken": []}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

WEB_STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(WEB_STATIC_DIR)), name="static")


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> ORJSONResponse:
    """处理业务逻辑异常，返回带状态码的标准错误响应"""
    return ORJSONResponse(status_code=exc.status_code, content=error_response(exc.message, exc.errors))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> ORJSONResponse:
    """处理请求参数校验失败，返回 422 错误"""
    return ORJSONResponse(status_code=422, content=error_response("validation error", exc.errors()))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> ORJSONResponse:
    """兜底异常处理器：记录未捕获的服务端错误并返回 500"""
    logger.exception("Unhandled server error", exc_info=exc)
    return ORJSONResponse(status_code=500, content=error_response("internal server error"))


# 注册所有路由模块
app.include_router(demo_router)        # 交互式演示 UI
app.include_router(health_router)      # 健康检查
app.include_router(google_crawler_router)  # Googlebot / Google Render 测试
app.include_router(discovery_router)   # 站点快照
app.include_router(audit_router)       # 各审计模块
app.include_router(task_router)        # 异步任务管理
app.include_router(report_router)      # 报告导出
app.include_router(token_admin_router)

if __name__ == "__main__":
    import uvicorn
    # 注意这里要写 "app.main:app" 而不是 "main:app"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8023, reload=True)
