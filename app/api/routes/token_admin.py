from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.responses import success_response
from app.services.infra.demo_tokens import demo_token_store


router = APIRouter(tags=["token-admin"])
TOKEN_ADMIN_HEADER = "X-Token-Admin-Key"
TOKEN_ADMIN_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "web" / "templates" / "token-admin.html"


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    token: str | None = Field(default=None, min_length=12, max_length=256)
    max_calls: int | None = Field(default=None, ge=1)


class UpdateTokenRequest(BaseModel):
    enabled: bool | None = None
    max_calls: int | None = Field(default=None, ge=1)
    reset_usage: bool = False


def require_token_admin(request: Request) -> None:
    expected = settings.token_admin_key
    if not expected:
        raise AppError(503, "token admin is not configured")
    provided = (request.headers.get(TOKEN_ADMIN_HEADER) or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise AppError(401, "token admin key required or invalid")


@router.get("/token-admin", response_class=HTMLResponse, include_in_schema=False)
async def token_admin_page() -> HTMLResponse:
    return HTMLResponse(TOKEN_ADMIN_TEMPLATE_PATH.read_text(encoding="utf-8"))


@router.get("/api/v1/admin/tokens/status", include_in_schema=False)
async def token_admin_status() -> dict:
    return success_response(
        {"configured": bool(settings.token_admin_key), "header_name": TOKEN_ADMIN_HEADER}
    )


@router.post("/api/v1/admin/tokens/verify", include_in_schema=False)
async def verify_token_admin(request: Request) -> dict:
    require_token_admin(request)
    return success_response({"verified": True})


@router.get("/api/v1/admin/tokens", include_in_schema=False)
async def list_demo_tokens(request: Request) -> dict:
    require_token_admin(request)
    return success_response(demo_token_store.list_tokens())


@router.post("/api/v1/admin/tokens", include_in_schema=False)
async def create_demo_token(request: Request, payload: CreateTokenRequest) -> dict:
    require_token_admin(request)
    try:
        token = demo_token_store.create_token(payload.name, payload.token, payload.max_calls)
    except ValueError as exc:
        raise AppError(409 if "already exists" in str(exc) else 422, str(exc)) from exc
    return success_response(token, message="token created")


@router.patch("/api/v1/admin/tokens/{token_id}", include_in_schema=False)
async def update_demo_token(token_id: int, request: Request, payload: UpdateTokenRequest) -> dict:
    require_token_admin(request)
    if not ({"enabled", "max_calls"} & payload.model_fields_set or payload.reset_usage):
        raise AppError(422, "at least one token setting is required")
    token = None
    if "enabled" in payload.model_fields_set:
        if payload.enabled is None:
            raise AppError(422, "enabled must be true or false")
        token = demo_token_store.set_enabled(token_id, payload.enabled)
    if "max_calls" in payload.model_fields_set:
        token = demo_token_store.set_limit(token_id, payload.max_calls)
    if payload.reset_usage:
        token = demo_token_store.reset_usage(token_id)
    if token is None:
        raise AppError(404, "token not found")
    return success_response(token, message="token updated")


@router.delete("/api/v1/admin/tokens/{token_id}", include_in_schema=False)
async def delete_demo_token(token_id: int, request: Request) -> dict:
    require_token_admin(request)
    if not demo_token_store.delete_token(token_id):
        raise AppError(404, "token not found")
    return success_response({"id": token_id}, message="token deleted")


@router.get("/api/v1/admin/token-logs", include_in_schema=False)
async def list_token_usage_logs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    token_id: int | None = Query(default=None, ge=1),
    auth_outcome: str | None = Query(default=None, max_length=40),
) -> dict:
    require_token_admin(request)
    return success_response(
        demo_token_store.list_usage_logs(
            limit=limit,
            offset=offset,
            token_id=token_id,
            auth_outcome=auth_outcome,
        )
    )


@router.delete("/api/v1/admin/token-logs", include_in_schema=False)
async def clear_token_usage_logs(request: Request) -> dict:
    require_token_admin(request)
    deleted = demo_token_store.clear_usage_logs()
    return success_response({"deleted": deleted}, message="token usage logs cleared")
