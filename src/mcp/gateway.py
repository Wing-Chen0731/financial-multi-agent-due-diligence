from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.rag.service import retrieve_context
from src.tools.financial_tools import calculate_financial_ratios, query_customer
from src.tools.news_tools import search_industry_news


class ToolGateway:
    """1+1+N architecture boundary: allow-listed tools with an audit trail."""

    def __init__(self):
        self._tools: dict[str, Callable[..., dict[str, Any]]] = {
            "crm.query_customer": query_customer,
            "finance.calculate_ratios": calculate_financial_ratios,
            "industry.search_news": search_industry_news,
            "knowledge.retrieve": retrieve_context,
        }
        self.audit_log: list[dict[str, Any]] = []

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP ``tools/list`` definitions for the allow-listed tools."""
        return [
            {
                "name": "crm.query_customer",
                "description": "查询本地演示 CRM 客户资料，不推断未返回的事实。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"customer_name": {"type": "string"}},
                    "required": ["customer_name"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "finance.calculate_ratios",
                "description": "根据用户提供的收入、利润和负债计算透明基础指标。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "revenue_wan": {"type": ["number", "null"]},
                        "debt_wan": {"type": ["number", "null"]},
                        "profit_wan": {"type": ["number", "null"]},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "industry.search_news",
                "description": "查询演示行业新闻线索，不替代正式事实核验。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "industry": {"type": "string"},
                        "keywords": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "knowledge.retrieve",
                "description": "检索金融知识库并返回带来源的辅助依据。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        ]

    def call(self, name: str, **params: Any) -> dict[str, Any]:
        if name not in self._tools:
            raise PermissionError(f"工具未在 MCP Gateway 白名单中：{name}")
        result = self._tools[name](**params)
        self.audit_log.append({"tool": name, "params": params, "ok": True})
        return result
