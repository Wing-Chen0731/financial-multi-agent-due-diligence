from __future__ import annotations

from typing import Any

import httpx


class MCPClient:
    """Minimal JSON-RPC MCP tools client over a Streamable-HTTP-style endpoint."""

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 30.0):
        endpoint = base_url.rstrip("/")
        self.endpoint = endpoint if endpoint.endswith("/mcp") else f"{endpoint}/mcp"
        self.token = token
        self.timeout = timeout
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    async def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {"initialized": True}
        result = await self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "financial-multi-agent", "version": "0.1.0"},
            },
        )
        self._initialized = True
        await self._notify("notifications/initialized")
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        await self.initialize()
        result = await self._request("tools/list", {})
        return list(result.get("tools", []))

    async def call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()
        result = await self._request("tools/call", {"name": tool_name, "arguments": params})
        if result.get("isError"):
            raise RuntimeError(f"MCP 工具调用失败：{tool_name}")
        return result.get("structuredContent", result)

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        response = await self._post(payload)
        body = response.json()
        if "error" in body:
            error = body["error"]
            raise RuntimeError(f"MCP {method} 错误：{error.get('message', 'unknown error')}")
        return body.get("result", {})

    async def _notify(self, method: str) -> None:
        await self._post({"jsonrpc": "2.0", "method": method})

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()
            self._session_id = response.headers.get("Mcp-Session-Id", self._session_id)
            return response
