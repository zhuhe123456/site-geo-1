from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.api.demo_access import API_TOKEN_HEADER, DEMO_TOKEN_HEADER, is_demo_token_enabled, require_demo_token
from app.api.routes.report import build_task_report_response
from app.api.routes.tasks import build_pending_graph_payload, task_service
from app.core.exceptions import AppError
from app.models.responses import success_response
from app.models.task import TaskAuditRequest

# Demo 路由：返回模板化后的交互式 GEO 审计控制台页面
router = APIRouter(tags=["demo"])

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "web" / "templates" / "demo.html"
GOOGLE_CRAWLER_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "web" / "templates" / "google-crawler.html"
API_DOC_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "web" / "templates" / "api-doc.html"
API_DOC_START = "<!-- API_DOC_START -->"
API_DOC_END = "<!-- API_DOC_END -->"


def _load_demo_and_api_content() -> tuple[str, str]:
    """从单一模板源拆分交互首页与独立 API 文档内容。"""
    source = TEMPLATE_PATH.read_text(encoding="utf-8")
    start = source.index(API_DOC_START)
    end = source.index(API_DOC_END) + len(API_DOC_END)
    api_content = source[start + len(API_DOC_START) : source.index(API_DOC_END)]
    demo_content = f"{source[:start]}{source[end:]}"
    return demo_content, api_content


@router.get("/", response_class=HTMLResponse)
async def demo_page() -> HTMLResponse:
    """返回 demo 模板页面。

    页面主体、样式和脚本都已拆分到:
    - app/web/templates/demo.html
    - app/web/static/css/demo.css
    - app/web/static/js/demo/
    """
    demo_content, _ = _load_demo_and_api_content()
    return HTMLResponse(demo_content)


@router.get("/google-crawler-test", response_class=HTMLResponse)
async def google_crawler_demo_page() -> HTMLResponse:
    """返回 Googlebot / Google Render 双检测 demo。"""
    return HTMLResponse(GOOGLE_CRAWLER_TEMPLATE_PATH.read_text(encoding="utf-8"))


@router.get("/api-doc", response_class=HTMLResponse)
async def api_doc_page() -> HTMLResponse:
    """返回产品化 API 调用说明页，Swagger 交互测试仍位于 /docs。"""
    _, api_content = _load_demo_and_api_content()
    shell = API_DOC_TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(shell.replace("{{API_DOC_CONTENT}}", api_content))


@router.get("/api/v1/demo/token-status", include_in_schema=False)
async def demo_token_status() -> dict:
    """返回 demo token 保护状态，不暴露真实 token。"""
    return success_response(
        {
            "token_required": is_demo_token_enabled(),
            "header_name": API_TOKEN_HEADER,
            "accepted_headers": [API_TOKEN_HEADER, DEMO_TOKEN_HEADER, "Authorization: Bearer"],
        }
    )


@router.post("/api/v1/demo/verify-token", include_in_schema=False)
async def verify_demo_token(request: Request) -> dict:
    """校验 demo token，用于页面显式解锁按钮。"""
    require_demo_token(request)
    return success_response(
        {
            "token_required": is_demo_token_enabled(),
            "verified": True,
        }
    )


@router.post("/api/v1/demo/tasks/audit", include_in_schema=False)
async def create_demo_audit_task(request: Request, payload: TaskAuditRequest) -> dict:
    """demo 页专用创建任务入口，要求携带 demo token。"""
    require_demo_token(request)
    task = await task_service.create_task(payload)
    return success_response(task.model_dump(mode="json"))


@router.get("/api/v1/demo/tasks/{task_id}", include_in_schema=False)
async def get_demo_audit_task(task_id: str, request: Request) -> dict:
    """demo 页专用任务查询入口，要求携带 demo token。"""
    require_demo_token(request)
    task = await task_service.get_task(task_id)
    if not task:
        raise AppError(404, "task not found")
    return success_response(task.model_dump(mode="json"))


@router.get("/api/v1/demo/tasks/{task_id}/knowledge-graph", include_in_schema=False)
async def get_demo_task_knowledge_graph(task_id: str, request: Request) -> dict:
    """兼容旧接口：demo 页返回结构图谱数据。"""
    require_demo_token(request)
    return await _load_demo_graph(task_id, graph_kind="structure")


async def _load_demo_graph(task_id: str, *, graph_kind: str) -> dict:
    task = await task_service.get_task(task_id)
    graph_service = (
        task_service.site_entity_graph_service
        if graph_kind == "entity"
        else task_service.site_graph_service
    )
    graph_label = "Entity graph" if graph_kind == "entity" else "Structure graph"
    try:
        graph_payload = await graph_service.load_task_graph(task_id)
    except Exception:
        if task:
            return success_response(
                build_pending_graph_payload(
                    task,
                    f"{graph_label} is still being prepared for this task.",
                    graph_kind=graph_kind,
                )
            )
        raise
    if graph_payload is None:
        if task:
            return success_response(
                build_pending_graph_payload(
                    task,
                    f"{graph_label} has not been built for this task yet.",
                    graph_kind=graph_kind,
                )
            )
        raise AppError(404, f"task {graph_kind} graph not found")
    graph_payload["graph_kind"] = graph_kind
    return success_response(graph_payload)


@router.get("/api/v1/demo/tasks/{task_id}/structure-graph", include_in_schema=False)
async def get_demo_task_structure_graph(task_id: str, request: Request) -> dict:
    """demo 页专用结构图谱查询入口，要求携带 demo token。"""
    require_demo_token(request)
    return await _load_demo_graph(task_id, graph_kind="structure")


@router.get("/api/v1/demo/tasks/{task_id}/entity-graph", include_in_schema=False)
async def get_demo_task_entity_graph(task_id: str, request: Request) -> dict:
    """demo 页专用实体图谱查询入口，要求携带 demo token。"""
    require_demo_token(request)
    return await _load_demo_graph(task_id, graph_kind="entity")


@router.get("/api/v1/demo/tasks/{task_id}/report", response_class=PlainTextResponse, include_in_schema=False)
async def export_demo_task_report(task_id: str, request: Request) -> PlainTextResponse:
    """demo 页专用报告导出入口，要求携带 demo token。"""
    require_demo_token(request)
    return await build_task_report_response(task_id)
