from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode

from fastapi import Request
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.demo_access import authenticate_api_token, get_api_token
from app.models.responses import error_response
from app.services.infra.demo_tokens import demo_token_store


logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_SENSITIVE_QUERY_PARTS = ("token", "key", "secret", "password", "authorization", "auth")
_PUBLIC_API_PATHS = {
    "/api/v1/demo/token-status",
}
_ROUTE_AUTH_PATHS = {
    "/api/v1/demo/verify-token",
}


def _request_id(request: Request) -> str:
    supplied = (request.headers.get("X-Request-ID") or "").strip()
    return supplied if _REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex


def _safe_query_string(request: Request) -> str | None:
    if not request.url.query:
        return None
    safe_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(request.url.query, keep_blank_values=True):
        lowered = key.lower()
        safe_value = "[REDACTED]" if any(part in lowered for part in _SENSITIVE_QUERY_PARTS) else value[:256]
        safe_items.append((key[:128], safe_value))
    return urlencode(safe_items)[:2048]


def _header(request: Request, name: str, limit: int = 512) -> str | None:
    value = (request.headers.get(name) or "").strip()
    return value[:limit] or None


def _integer_header(response_or_request, name: str) -> int | None:
    value = response_or_request.headers.get(name)
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def should_audit_token_request(path: str) -> bool:
    return path.startswith("/api/v1/") and not path.startswith("/api/v1/admin/") and path not in _PUBLIC_API_PATHS


class ApiTokenAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not should_audit_token_request(path):
            return await call_next(request)

        started = time.perf_counter()
        request_id = _request_id(request)
        token, transport = get_api_token(request)
        auth = authenticate_api_token(token, transport, consume=path not in _ROUTE_AUTH_PATHS)
        request.state.api_token_auth = auth
        request.state.request_id = request_id

        if path not in _ROUTE_AUTH_PATHS and not auth["valid"]:
            status_code = 429 if auth["outcome"] == "quota-exceeded" else 401
            message = (
                "API token usage limit exceeded"
                if status_code == 429
                else "API token required or invalid"
            )
            response: Response = ORJSONResponse(
                status_code=status_code,
                content=error_response(message),
            )
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        route = request.scope.get("route")
        entry = {
            "request_id": request_id,
            "token_id": auth.get("token_id"),
            "token_name": auth.get("token_name"),
            "token_hint": auth.get("token_hint"),
            "auth_source": auth["source"],
            "auth_outcome": auth["outcome"],
            "credential_transport": auth["transport"],
            "method": request.method,
            "path": path[:1024],
            "route_name": getattr(route, "name", None),
            "query_string": _safe_query_string(request),
            "client_ip": request.client.host[:128] if request.client and request.client.host else None,
            "forwarded_for": _header(request, "X-Forwarded-For", 512),
            "user_agent": _header(request, "User-Agent", 1024),
            "referer": _header(request, "Referer", 1024),
            "content_type": _header(request, "Content-Type", 256),
            "request_bytes": _integer_header(request, "Content-Length"),
            "status_code": response.status_code,
            "response_bytes": _integer_header(response, "Content-Length"),
            "duration_ms": duration_ms,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            demo_token_store.log_usage(entry)
        except Exception:
            logger.exception("Failed to persist API token usage log", extra={"request_id": request_id})
        return response
