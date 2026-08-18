from __future__ import annotations

from typing import Any

DEMO_NEWS: list[dict[str, str]] = [
    {
        "title": "信息技术行业景气度跟踪（演示）",
        "industry": "信息技术",
        "summary": "演示资料：行业分析应结合订单、应收账款、现金流和客户集中度核验。",
        "source": "local_demo_news",
        "published_at": "2026-01-15",
    },
    {
        "title": "企业融资环境观察（演示）",
        "industry": "通用",
        "summary": "演示资料：外部新闻只能作为风险线索，不能替代企业一手财务和经营资料。",
        "source": "local_demo_news",
        "published_at": "2026-01-20",
    },
]


def search_industry_news(industry: str = "通用", keywords: str = "") -> dict[str, Any]:
    """Return local demo news; replace this boundary with an approved news API."""
    matches = [
        item for item in DEMO_NEWS
        if item["industry"] in {industry, "通用"}
        or any(keyword and keyword in item["summary"] for keyword in keywords.split())
    ]
    return {
        "items": matches[:5],
        "source": "local_demo_news",
        "warning": "演示新闻不是实时数据，生产环境需要接入有授权的新闻源并记录时间戳。",
    }
