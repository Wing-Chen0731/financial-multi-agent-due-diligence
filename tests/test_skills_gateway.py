import asyncio

import httpx
import pytest

from src.api.server import app
from src.mcp.gateway import ToolGateway
from src.skills.registry import get_skill_registry


def test_skill_registry_has_five_business_skills():
    registry = get_skill_registry()
    assert len(registry.all()) == 5
    assert "industry_news_search" in registry.recommend("查询行业新闻和舆情")


def test_tool_gateway_allowlist_and_audit():
    gateway = ToolGateway()
    result = gateway.call("finance.calculate_ratios", revenue_wan=100, profit_wan=10)
    assert result["profit_margin"] == 0.1
    assert gateway.audit_log[0]["tool"] == "finance.calculate_ratios"
    with pytest.raises(PermissionError):
        gateway.call("dangerous.delete_data")


def test_mcp_jsonrpc_tools_endpoint():
    async def exercise() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            initialize = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            )
            assert initialize.status_code == 200
            tools = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            names = {item["name"] for item in tools.json()["result"]["tools"]}
            assert "finance.calculate_ratios" in names
            called = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "finance.calculate_ratios", "arguments": {"revenue_wan": 100, "profit_wan": 10}},
                },
            )
            assert called.json()["result"]["structuredContent"]["profit_margin"] == 0.1

    asyncio.run(exercise())
