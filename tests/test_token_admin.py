from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.infra.demo_tokens import demo_token_store


client = TestClient(app)


@pytest.fixture()
def token_admin_settings(tmp_path: Path):
    original_admin_key = settings.token_admin_key
    original_db_path = settings.demo_token_db_path
    original_demo_token = settings.demo_access_token
    object.__setattr__(settings, "token_admin_key", "test-admin-secret")
    object.__setattr__(settings, "demo_token_db_path", str(tmp_path / "tokens.sqlite3"))
    object.__setattr__(settings, "demo_access_token", "")
    try:
        yield
    finally:
        object.__setattr__(settings, "token_admin_key", original_admin_key)
        object.__setattr__(settings, "demo_token_db_path", original_db_path)
        object.__setattr__(settings, "demo_access_token", original_demo_token)


def test_token_admin_page_and_assets_are_available() -> None:
    page = client.get("/token-admin")
    css = client.get("/static/css/token-admin.css")
    js = client.get("/static/js/token-admin.js")

    assert page.status_code == 200
    assert "访问 Token 管理" in page.text
    assert 'id="generate-token"' in page.text
    assert 'id="max-calls"' in page.text
    assert 'id="log-panel"' in page.text
    assert css.status_code == 200
    assert js.status_code == 200
    assert "crypto.getRandomValues" in js.text
    assert "openTokenLogs" in js.text
    assert "configureTokenLimit" in js.text


def test_admin_api_requires_independent_key(token_admin_settings) -> None:
    denied = client.get("/api/v1/admin/tokens")
    allowed = client.get(
        "/api/v1/admin/tokens",
        headers={"X-Token-Admin-Key": "test-admin-secret"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["data"] == []


def test_admin_can_create_disable_and_delete_demo_token(token_admin_settings) -> None:
    admin_headers = {"X-Token-Admin-Key": "test-admin-secret"}
    create = client.post(
        "/api/v1/admin/tokens",
        headers=admin_headers,
        json={"name": "Customer demo", "token": "customer-demo-secret"},
    )
    assert create.status_code == 200
    created = create.json()["data"]
    assert created["token"] == "customer-demo-secret"
    assert created["enabled"] is True

    listed = client.get("/api/v1/admin/tokens", headers=admin_headers).json()["data"]
    assert len(listed) == 1
    assert listed[0]["token"] == "customer-demo-secret"
    assert listed[0]["token_hint"] == "custom…cret"

    accepted = client.post(
        "/api/v1/demo/verify-token",
        headers={"X-Demo-Token": "customer-demo-secret"},
    )
    assert accepted.status_code == 200

    disabled = client.patch(
        f"/api/v1/admin/tokens/{created['id']}",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["data"]["enabled"] is False

    rejected = client.post(
        "/api/v1/demo/verify-token",
        headers={"X-Demo-Token": "customer-demo-secret"},
    )
    assert rejected.status_code == 401

    deleted = client.delete(
        f"/api/v1/admin/tokens/{created['id']}", headers=admin_headers
    )
    assert deleted.status_code == 200
    assert client.get("/api/v1/admin/tokens", headers=admin_headers).json()["data"] == []


def test_duplicate_token_is_rejected(token_admin_settings) -> None:
    headers = {"X-Token-Admin-Key": "test-admin-secret"}
    payload = {"name": "First", "token": "duplicate-secret"}
    assert client.post("/api/v1/admin/tokens", headers=headers, json=payload).status_code == 200

    duplicate = client.post(
        "/api/v1/admin/tokens",
        headers=headers,
        json={"name": "Second", "token": "duplicate-secret"},
    )
    assert duplicate.status_code == 409


def test_token_pause_and_usage_limit_are_enforced(token_admin_settings) -> None:
    admin_headers = {"X-Token-Admin-Key": "test-admin-secret"}
    token_headers = {"X-API-Token": "limited-client-token"}
    create = client.post(
        "/api/v1/admin/tokens",
        headers=admin_headers,
        json={"name": "Limited client", "token": "limited-client-token", "max_calls": 2},
    )
    assert create.status_code == 200
    created = create.json()["data"]
    assert created["max_calls"] == 2
    assert created["used_calls"] == 0
    assert created["remaining_calls"] == 2

    # Token 验证接口不应占用业务调用次数。
    assert client.post("/api/v1/demo/verify-token", headers=token_headers).status_code == 200
    after_verify = client.get("/api/v1/admin/tokens", headers=admin_headers).json()["data"][0]
    assert after_verify["used_calls"] == 0
    assert client.get("/api/v1/tasks/missing-1", headers=token_headers).status_code == 404
    assert client.get("/api/v1/tasks/missing-2", headers=token_headers).status_code == 404
    exhausted = client.get(
        "/api/v1/tasks/missing-3",
        headers={**token_headers, "X-Request-ID": "quota-exhausted-request"},
    )
    assert exhausted.status_code == 429

    listed = client.get("/api/v1/admin/tokens", headers=admin_headers).json()["data"][0]
    assert listed["used_calls"] == 2
    assert listed["remaining_calls"] == 0
    quota_log = demo_token_store.list_usage_logs(auth_outcome="quota-exceeded")["items"][0]
    assert quota_log["request_id"] == "quota-exhausted-request"
    assert quota_log["token_id"] == created["id"]
    assert quota_log["status_code"] == 429

    reset_and_pause = client.patch(
        f"/api/v1/admin/tokens/{created['id']}",
        headers=admin_headers,
        json={"enabled": False, "reset_usage": True},
    )
    assert reset_and_pause.status_code == 200
    assert reset_and_pause.json()["data"]["enabled"] is False
    assert reset_and_pause.json()["data"]["used_calls"] == 0
    assert client.get("/api/v1/tasks/paused", headers=token_headers).status_code == 401

    unlimited = client.patch(
        f"/api/v1/admin/tokens/{created['id']}",
        headers=admin_headers,
        json={"enabled": True, "max_calls": None},
    )
    assert unlimited.status_code == 200
    assert unlimited.json()["data"]["max_calls"] is None
    assert client.get("/api/v1/tasks/unlimited", headers=token_headers).status_code == 404


def test_business_api_requires_token_and_records_complete_usage_logs(token_admin_settings) -> None:
    created = demo_token_store.create_token("Integration client", "integration-client-token")

    missing = client.get("/api/v1/tasks/not-found")
    invalid = client.get(
        "/api/v1/tasks/not-found",
        headers={"X-API-Token": "wrong-token-value", "X-Request-ID": "invalid-request"},
    )
    valid = client.get(
        "/api/v1/tasks/not-found?api_token=must-not-be-logged&view=summary",
        headers={
            "X-API-Token": "integration-client-token",
            "X-Request-ID": "valid-request",
            "User-Agent": "token-test-agent/1.0",
        },
    )
    legacy = client.get(
        "/api/v1/tasks/not-found",
        headers={"X-Demo-Token": "integration-client-token"},
    )
    bearer = client.get(
        "/api/v1/tasks/not-found",
        headers={"Authorization": "Bearer integration-client-token"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 404
    assert valid.headers["X-Request-ID"] == "valid-request"
    assert legacy.status_code == 404
    assert bearer.status_code == 404

    logs = demo_token_store.list_usage_logs(limit=20)["items"]
    assert len(logs) == 5
    by_request_id = {item["request_id"]: item for item in logs}
    assert by_request_id["invalid-request"]["auth_outcome"] == "invalid"
    assert by_request_id["invalid-request"]["token_hint"] is None

    successful = by_request_id["valid-request"]
    assert successful["token_id"] == created["id"]
    assert successful["token_name"] == "Integration client"
    assert successful["auth_source"] == "sqlite"
    assert successful["auth_outcome"] == "valid"
    assert successful["credential_transport"] == "x-api-token"
    assert successful["method"] == "GET"
    assert successful["path"] == "/api/v1/tasks/not-found"
    assert successful["query_string"] == "api_token=%5BREDACTED%5D&view=summary"
    assert successful["status_code"] == 404
    assert successful["duration_ms"] >= 0
    assert successful["user_agent"] == "token-test-agent/1.0"
    assert successful["request_bytes"] is None
    assert any(item["credential_transport"] == "x-demo-token" for item in logs)
    assert any(item["credential_transport"] == "bearer" for item in logs)


def test_admin_can_query_and_clear_usage_logs(token_admin_settings) -> None:
    demo_token_store.create_token("Log client", "log-client-secret")
    client.get("/api/v1/tasks/missing", headers={"X-API-Token": "log-client-secret"})
    headers = {"X-Token-Admin-Key": "test-admin-secret"}

    response = client.get("/api/v1/admin/token-logs?auth_outcome=valid", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["token_name"] == "Log client"

    cleared = client.delete("/api/v1/admin/token-logs", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted"] == 1
    assert demo_token_store.list_usage_logs()["total"] == 0


def test_openapi_documents_api_token_header() -> None:
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["ApiToken"]["name"] == "X-API-Token"
    assert schema["paths"]["/api/v1/discovery"]["post"]["security"] == [{"ApiToken": []}]
