from __future__ import annotations

import re
from typing import Any

CUSTOMERS: dict[str, dict[str, Any]] = {
    "示例科技有限公司": {
        "company_name": "示例科技有限公司",
        "industry": "信息技术",
        "established": "2018-03-15",
        "credit_rating": "AA（演示数据）",
        "annual_revenue_wan": 5000,
        "source": "本地演示数据，不代表真实客户资料",
    }
}


def extract_customer_name(query: str) -> str:
    """Extract a Chinese company name conservatively."""
    cleaned = re.sub(r"^(?:请|帮我)?(?:对|给|查询|分析|评估|调查)\s*", "", query)
    match = re.search(r"([一-鿿A-Za-z0-9（）()·]{2,30}(?:有限公司|集团|银行|公司))", cleaned)
    return match.group(1) if match else ""


def query_customer(customer_name: str) -> dict[str, Any]:
    """Return mock CRM data; replace this boundary with a permissioned CRM API."""
    if not customer_name:
        return {"found": False, "error": "未识别到客户名称", "source": "local_demo_crm"}
    record = CUSTOMERS.get(customer_name)
    if not record:
        return {
            "found": False,
            "error": "本地演示 CRM 未找到该客户；不能据此推断客户情况",
            "customer_name": customer_name,
            "source": "local_demo_crm",
        }
    return {"found": True, "data": record}


def calculate_financial_ratios(
    revenue_wan: float | None = None,
    debt_wan: float | None = None,
    profit_wan: float | None = None,
) -> dict[str, Any]:
    """Calculate transparent, non-decisional ratios from supplied numbers."""
    result: dict[str, Any] = {"source": "user_supplied_values"}
    if revenue_wan == 0:
        result["error"] = "收入不能为 0，无法计算利润率或债务收入比"
        return result
    if revenue_wan is not None and profit_wan is not None:
        result["profit_margin"] = round(profit_wan / revenue_wan, 4)
    if revenue_wan is not None and debt_wan is not None:
        result["debt_to_revenue"] = round(debt_wan / revenue_wan, 4)
    if len(result) == 1:
        result["error"] = "至少需要提供可用的收入、负债或利润数据"
    return result


def extract_financial_values(query: str) -> dict[str, float]:
    """Extract explicitly labelled user values for the transparent ratio tool."""
    patterns = {
        "revenue_wan": r"(?:营业收入|收入|营收)\s*[:：=]?\s*(-?\d+(?:\.\d+)?)",
        "profit_wan": r"(?:净利润|利润)\s*[:：=]?\s*(-?\d+(?:\.\d+)?)",
        "debt_wan": r"(?:负债|债务)\s*[:：=]?\s*(-?\d+(?:\.\d+)?)",
    }
    values: dict[str, float] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, query)
        if match:
            values[name] = float(match.group(1))
    return values
