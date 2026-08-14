from __future__ import annotations

import hmac

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.infra.demo_tokens import demo_token_store


API_TOKEN_HEADER = "X-API-Token"
DEMO_TOKEN_HEADER = "X-Demo-Token"


def get_demo_access_tokens() -> tuple[str, ...]:
    """读取逗号分隔的 demo token 白名单，并忽略空项。"""
    return tuple(
        token
        for item in settings.demo_access_token.split(",")
        if (token := item.strip())
    )


def is_demo_token_enabled() -> bool:
    """当前环境是否启用了 demo token 保护。"""
    return settings.api_token_required or bool(get_demo_access_tokens()) or demo_token_store.has_tokens()


def get_api_token(request: Request) -> tuple[str | None, str]:
    preferred = request.headers.get(API_TOKEN_HEADER)
    if preferred:
        return preferred, "x-api-token"
    legacy = request.headers.get(DEMO_TOKEN_HEADER)
    if legacy:
        return legacy, "x-demo-token"
    authorization = (request.headers.get("Authorization") or "").strip()
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() == "bearer" and credential.strip():
        return credential.strip(), "bearer"
    return None, "missing"


def authenticate_api_token(
    token: str | None, transport: str = "unknown", *, consume: bool = True
) -> dict:
    protection_enabled = is_demo_token_enabled()
    if not protection_enabled:
        return {
            "valid": True,
            "outcome": "protection-disabled",
            "source": "disabled",
            "transport": transport,
            "token_id": None,
            "token_name": None,
            "token_hint": None,
        }

    provided = (token or "").strip()
    if not provided:
        return {
            "valid": False,
            "outcome": "missing",
            "source": "none",
            "transport": transport,
            "token_id": None,
            "token_name": None,
            "token_hint": None,
        }

    for index, allowed in enumerate(get_demo_access_tokens(), start=1):
        if hmac.compare_digest(provided, allowed):
            return {
                "valid": True,
                "outcome": "valid",
                "source": "environment",
                "transport": transport,
                "token_id": None,
                "token_name": f"Environment token {index}",
                "token_hint": f"{provided[:6]}…{provided[-4:]}",
            }

    resolved = demo_token_store.resolve_token(provided, consume=consume)
    if resolved:
        valid = resolved["enabled"] and not resolved["quota_exceeded"]
        outcome = (
            "disabled"
            if not resolved["enabled"]
            else "quota-exceeded"
            if resolved["quota_exceeded"]
            else "valid"
        )
        return {
            "valid": valid,
            "outcome": outcome,
            "source": "sqlite",
            "transport": transport,
            "token_id": resolved["id"],
            "token_name": resolved["name"],
            "token_hint": resolved["token_hint"],
            "max_calls": resolved["max_calls"],
            "used_calls": resolved["used_calls"],
        }
    return {
        "valid": False,
        "outcome": "invalid",
        "source": "unknown",
        "transport": transport,
        "token_id": None,
        "token_name": None,
        "token_hint": None,
    }


def has_valid_demo_token(token: str | None) -> bool:
    """校验请求携带的 demo token。未启用时默认放行。"""
    return bool(authenticate_api_token(token, "legacy-call")["valid"])


def get_demo_token(request: Request) -> str | None:
    """从请求头读取 demo token。"""
    return get_api_token(request)[0]


def require_api_token(request: Request) -> dict:
    existing = getattr(request.state, "api_token_auth", None)
    if existing is None:
        token, transport = get_api_token(request)
        existing = authenticate_api_token(token, transport)
        request.state.api_token_auth = existing
    if existing["valid"]:
        return existing
    if existing["outcome"] == "quota-exceeded":
        raise AppError(429, "API token usage limit exceeded")
    raise AppError(401, "API token required or invalid")


def require_demo_token(request: Request) -> None:
    """在启用 demo token 时强制校验请求头。"""
    existing = getattr(request.state, "api_token_auth", None)
    if existing is None:
        token, transport = get_api_token(request)
        existing = authenticate_api_token(token, transport)
        request.state.api_token_auth = existing
    if existing["valid"]:
        return
    if existing["outcome"] == "quota-exceeded":
        raise AppError(429, "API token usage limit exceeded")
    raise AppError(401, "demo token required or invalid")
