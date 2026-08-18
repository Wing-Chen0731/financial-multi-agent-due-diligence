from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.graph import invoke_graph
from src.mcp.gateway import ToolGateway
from src.mcp.protocol import jsonrpc_error, jsonrpc_result, tool_call_result
from src.models.llm import readiness_info, runtime_info

app = FastAPI(title="金融多智能体系统", version="0.1.0")
WEB_DIR = Path(__file__).resolve().parents[2] / "web"

if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    task_type: str
    confidence: float
    need_human_review: bool
    trace: list[str]
    selected_skills: list[str] = Field(default_factory=list)
    prompt_version: str = "unknown"
    execution_mode: str = "fast"
    runtime: dict = Field(default_factory=dict)
    sources: list[dict] = Field(default_factory=list)
    collected_data: dict = Field(default_factory=dict)
    customer_data_status: dict = Field(default_factory=dict)
    industry_news: dict = Field(default_factory=dict)
    tool_trace: list[dict] = Field(default_factory=list)
    risk_analysis: dict = Field(default_factory=dict)
    compliance_review: dict = Field(default_factory=dict)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", **runtime_info()}


@app.get("/readiness")
def readiness() -> dict[str, Any]:
    return readiness_info()


def _mcp_authorized(request: Request) -> bool:
    expected = os.getenv("MCP_AUTH_TOKEN")
    if not expected:
        return True
    return request.headers.get("Authorization") == f"Bearer {expected}"


@app.post("/mcp")
async def mcp_endpoint(request: Request) -> Response:
    """Expose allow-listed tools through a minimal MCP JSON-RPC endpoint."""
    if not _mcp_authorized(request):
        return JSONResponse(jsonrpc_error(None, -32001, "MCP authorization required"), status_code=401)
    message = await request.json()
    request_id = message.get("id")
    method = message.get("method")
    gateway = ToolGateway()
    if method == "initialize":
        params = message.get("params", {})
        return JSONResponse(jsonrpc_result(request_id, {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "financial-multi-agent", "version": "0.1.0"},
        }))
    if method == "notifications/initialized":
        return Response(status_code=204)
    if method == "tools/list":
        return JSONResponse(jsonrpc_result(request_id, {"tools": gateway.tool_definitions()}))
    if method == "tools/call":
        params = message.get("params", {})
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or tool_name not in gateway.list_tools():
            return JSONResponse(jsonrpc_error(request_id, -32602, "Unknown or invalid tool name"), status_code=400)
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return JSONResponse(jsonrpc_error(request_id, -32602, "Tool arguments must be an object"), status_code=400)
        try:
            result = gateway.call(tool_name, **arguments)
            return JSONResponse(jsonrpc_result(request_id, tool_call_result(result)))
        except Exception as exc:  # noqa: BLE001 - return an MCP tool-level error
            return JSONResponse(jsonrpc_result(request_id, {
                "content": [{"type": "text", "text": "工具执行失败，请检查工具参数或服务日志。"}],
                "isError": True,
                "_error_type": type(exc).__name__,
            }))
    return JSONResponse(jsonrpc_error(request_id, -32601, "Method not found"), status_code=404)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = invoke_graph(request.message)
        return ChatResponse(
            response=result.get("final_report", ""),
            task_type=result.get("task_type", "general_chat"),
            confidence=result.get("confidence", 0.0),
            need_human_review=result.get("need_human_review", False),
            trace=result.get("trace", []),
            selected_skills=result.get("selected_skills", []),
            prompt_version=result.get("prompt_version", "unknown"),
            execution_mode=result.get("execution_mode", "fast"),
            runtime=result.get("runtime", runtime_info()),
            sources=result.get("retrieved_context", []),
            collected_data=result.get("collected_data", {}),
            customer_data_status=result.get("customer_data_status", {}),
            industry_news=result.get("industry_news", {}),
            tool_trace=result.get("tool_trace", []),
            risk_analysis=result.get("risk_analysis", {}),
            compliance_review=result.get("compliance_review", {}),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
