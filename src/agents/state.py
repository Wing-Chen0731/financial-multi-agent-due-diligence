from __future__ import annotations

from typing import Any, TypedDict


class FinancialState(TypedDict, total=False):
    """Shared state passed through the LangGraph workflow."""

    user_query: str
    task_type: str
    selected_skills: list[str]
    skill_context: str
    prompt_version: str
    execution_mode: str
    runtime: dict[str, str]
    customer_name: str
    customer_data_status: dict[str, Any]
    messages: list[dict[str, str]]
    collected_data: dict[str, Any]
    industry_news: dict[str, Any]
    tool_trace: list[dict[str, Any]]
    retrieved_context: list[dict[str, Any]]
    risk_analysis: dict[str, Any]
    compliance_review: dict[str, Any]
    final_report: str
    confidence: float
    need_human_review: bool
    trace: list[str]
    error: str
