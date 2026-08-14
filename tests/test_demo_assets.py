from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes import demo as demo_routes
from app.core.config import settings
from app.main import app
from app.models.task import AuditTask


client = TestClient(app)


def test_demo_page_serves_template_assets() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert '/static/css/demo.css' in response.text
    assert '/static/css/audit-refresh.css' in response.text
    assert '/static/js/demo/index.js' in response.text
    assert 'href="/api-doc"' in response.text
    assert 'API 调用步骤' not in response.text


def test_demo_static_assets_are_mounted() -> None:
    css_response = client.get("/static/css/demo.css")
    refresh_css_response = client.get("/static/css/audit-refresh.css")
    js_response = client.get("/static/js/demo/index.js")
    assert css_response.status_code == 200
    assert refresh_css_response.status_code == 200
    assert js_response.status_code == 200


def test_api_doc_is_separate_and_links_to_interactive_docs() -> None:
    response = client.get("/api-doc")
    assert response.status_code == 200
    assert "API 调用步骤" in response.text
    assert "Google 爬虫测试 API" in response.text
    assert 'href="/docs"' in response.text
    assert "立即测试 API" in response.text


def test_openapi_hides_demo_task_routes_and_exposes_split_graph_routes() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    paths = payload["paths"]
    assert "/api/v1/tasks/{task_id}/knowledge-graph" in paths
    assert "/api/v1/tasks/{task_id}/structure-graph" in paths
    assert "/api/v1/tasks/{task_id}/entity-graph" in paths
    assert "/api/v1/demo/tasks/audit" not in paths
    assert "/api/v1/demo/tasks/{task_id}" not in paths
    assert "/api/v1/demo/tasks/{task_id}/structure-graph" not in paths


def test_demo_token_status_reports_enabled_flag() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        response = client.get("/api/v1/demo/token-status")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["token_required"] is True
    assert payload["data"]["header_name"] == "X-Demo-Token"


def test_demo_verify_token_requires_matching_header() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        denied = client.post("/api/v1/demo/verify-token")
        allowed = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "demo-secret"})
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert denied.status_code == 401
    assert denied.json()["message"] == "demo token required or invalid"
    assert allowed.status_code == 200
    assert allowed.json()["data"]["verified"] is True


def test_demo_verify_token_accepts_any_token_from_comma_separated_whitelist() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "first-secret, second-secret, ,third-secret")
    try:
        first = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "first-secret"})
        second = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "second-secret"})
        third = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "third-secret"})
        denied = client.post("/api/v1/demo/verify-token", headers={"X-Demo-Token": "unknown-secret"})
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert denied.status_code == 401


def test_demo_task_routes_reject_missing_token_when_enabled() -> None:
    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "demo-secret")
    try:
        response = client.get("/api/v1/demo/tasks/non-existent-task")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 401
    assert response.json()["message"] == "demo token required or invalid"


def test_demo_knowledge_graph_returns_pending_payload_when_snapshot_not_ready(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    task = AuditTask(
        task_id="task-pending-graph",
        url="https://example.com/",
        normalized_url="https://example.com/",
        domain="example.com",
        cache_key="cache-key",
        task_type="site_geo_audit",
        mode="standard",
        build_knowledge_graph=True,
        storage_backend="mysql",
        created_at=now,
        updated_at=now,
        step_order=[],
        steps={},
    )

    async def fake_get_task(task_id: str):
        return task

    async def fake_load_task_graph(task_id: str):
        return None

    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "")
    monkeypatch.setattr(demo_routes.task_service, "get_task", fake_get_task)
    monkeypatch.setattr(demo_routes.task_service.site_graph_service, "load_task_graph", fake_load_task_graph)
    monkeypatch.setattr(demo_routes.task_service.site_graph_service, "enabled", True)
    try:
        response = client.get("/api/v1/demo/tasks/task-pending-graph/knowledge-graph")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["built"] is False
    assert payload["data"]["available"] is True
    assert "not been built" in payload["data"]["note"]
    assert payload["data"]["graph_kind"] == "structure"


def test_demo_entity_graph_returns_pending_payload_when_snapshot_not_ready(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    task = AuditTask(
        task_id="task-pending-entity-graph",
        url="https://example.com/",
        normalized_url="https://example.com/",
        domain="example.com",
        cache_key="cache-key",
        task_type="site_geo_audit",
        mode="standard",
        build_knowledge_graph=True,
        storage_backend="mysql",
        created_at=now,
        updated_at=now,
        step_order=[],
        steps={},
    )

    async def fake_get_task(task_id: str):
        return task

    async def fake_load_task_graph(task_id: str):
        return None

    original = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "")
    monkeypatch.setattr(demo_routes.task_service, "get_task", fake_get_task)
    monkeypatch.setattr(demo_routes.task_service.site_entity_graph_service, "load_task_graph", fake_load_task_graph)
    monkeypatch.setattr(demo_routes.task_service.site_entity_graph_service, "enabled", True)
    try:
        response = client.get("/api/v1/demo/tasks/task-pending-entity-graph/entity-graph")
    finally:
        object.__setattr__(settings, "demo_access_token", original)

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["built"] is False
    assert payload["data"]["available"] is True
    assert payload["data"]["graph_kind"] == "entity"
    assert "not been built" in payload["data"]["note"]
