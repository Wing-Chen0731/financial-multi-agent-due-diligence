from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from src.agents.prompts import (
    COMPLIANCE_PROMPT,
    DATA_COLLECTOR_PROMPT,
    PROMPT_VERSION,
    REPORT_PROMPT,
    RISK_PROMPT,
    SUPERVISOR_PROMPT,
)
from src.agents.state import FinancialState
from src.mcp.gateway import ToolGateway
from src.models.llm import execution_mode, get_llm, runtime_info
from src.skills.registry import get_skill_registry
from src.tools.financial_tools import extract_customer_name, extract_financial_values


def _content(response: Any) -> str:
    return str(getattr(response, "content", response))


def _ask(llm: Any, system: str, user: str) -> str:
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return _content(response)


def _task_type(query: str) -> str:
    investment_markers = (
        "股票", "基金", "买入", "卖出", "投资建议", "收益", "收益承诺", "投资组合",
        "投资配置", "资产配置", "择股", "保本", "保证收益", "本金保障", "仓位",
    )
    if any(word in query for word in investment_markers):
        return "investment_query"
    if "投资" in query and any(word in query for word in ("风险", "建议", "推荐", "适合", "承受", "组合", "配置")):
        return "investment_query"
    compliance_markers = ("制度", "规定", "监管", "条款", "依据")
    due_diligence_actions = ("尽调", "贷款", "风险报告", "还款", "担保", "贷前", "债务")
    if any(word in query for word in compliance_markers) and not any(
        word in query for word in due_diligence_actions
    ):
        return "compliance_query"
    if any(word in query for word in ("尽调", "授信", "贷款", "风险报告", "还款", "担保", "贷前")):
        return "due_diligence"
    if "债务" in query and "风险" in query:
        return "due_diligence"
    if any(word in query for word in ("制度", "规定", "监管", "合规", "条款", "反洗钱", "身份", "保存")):
        return "compliance_query"
    return "general_chat"


def _supervisor_task(model: Any, query: str) -> str:
    """Use the Supervisor prompt when the model returns valid JSON; keep rules as fallback."""
    rule_task = _task_type(query)
    if execution_mode() == "fast":
        return rule_task
    try:
        raw = _ask(model, f"{SUPERVISOR_PROMPT}\n请严格输出 JSON。", query)
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            task_type = json.loads(raw[start : end + 1]).get("task_type")
            if task_type in {"general_chat", "due_diligence", "compliance_query", "investment_query"}:
                # Deterministic safety rules remain authoritative for high-risk intents.
                if rule_task in {"investment_query", "due_diligence"}:
                    return rule_task
                return task_type
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return _task_type(query)


def _fast_collection_note(customer: dict[str, Any], news: dict[str, Any], context: list[dict[str, Any]]) -> str:
    found = customer.get("found", False)
    customer_text = "已找到演示 CRM 客户记录" if found else "演示 CRM 未找到完整客户记录"
    source_text = f"知识库返回 {len(context)} 条依据" if context else "知识库未返回可引用依据"
    news_text = f"行业新闻工具返回 {len(news.get('items', []))} 条演示信息" if isinstance(news, dict) else "未调用行业新闻工具"
    return f"{customer_text}；{source_text}；{news_text}。不补写缺失事实，需人工核验。"


def _customer_data_status(customer: dict[str, Any], customer_name: str) -> dict[str, Any]:
    """Create a machine-readable data gate for the lending due-diligence flow."""
    if customer.get("found"):
        return {
            "status": "found",
            "label": "已找到 CRM 记录",
            "customer_name": customer_name,
            "source": customer.get("data", {}).get("source", "local_demo_crm"),
            "can_form_lending_conclusion": False,
            "missing_materials": [],
            "next_actions": ["继续核验财务、流水、担保和征信材料", "由有权人员完成最终判断"],
        }
    return {
        "status": "not_found",
        "label": "资料待补充",
        "customer_name": customer_name or "未识别客户",
        "source": customer.get("source", "local_demo_crm"),
        "can_form_lending_conclusion": False,
        "missing_materials": [
            {"name": "主体资格材料", "detail": "营业执照、统一社会信用代码、法定代表人及授权材料"},
            {"name": "财务与现金流材料", "detail": "近三年财务报表、近期经营数据、银行流水及主要回款来源"},
            {"name": "债务与还款材料", "detail": "存量融资、或有负债、还款来源和重大合同"},
            {"name": "担保与增信材料", "detail": "担保合同、抵质押物权属证明及评估材料"},
        ],
        "next_actions": [
            "请客户经理补录 CRM 客户档案或上传上述材料",
            "接入已授权的工商、征信、财务或核心系统数据源",
            "材料齐备后由有权人员进行人工复核和最终判断",
        ],
    }


def _missing_customer_report(state: FinancialState) -> str:
    status = state.get("customer_data_status", {})
    customer_name = status.get("customer_name", "未识别客户")
    materials = status.get("missing_materials", [])
    actions = status.get("next_actions", [])
    lines = [
        "## 授信尽调：资料待补充",
        "",
        f"**客户：** {customer_name}",
        f"**数据状态：** {status.get('label', '资料待补充')}",
        "",
        "当前客户未在本地演示 CRM 中找到，系统不能凭模型记忆补写企业信息，也不能据此形成确定性的授信批准、拒绝或额度结论。",
        "",
        "### 缺失材料",
    ]
    for item in materials:
        lines.append(f"- **{item['name']}**：{item['detail']}")
    lines.extend(["", "### 下一步处理"])
    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. {action}")
    lines.extend([
        "",
        "### 结论边界",
        "- 当前仅能输出资料完整性提示和补件清单。",
        "- 补件完成前，授信结论状态为“不可形成”，需人工复核。",
        "- 接入外部数据时必须具备授权、来源、时间戳和可追溯记录。",
    ])
    return "\n".join(lines)


def _fast_risk_analysis(state: FinancialState) -> str:
    customer = state.get("collected_data", {}).get("customer", {})
    context = state.get("retrieved_context", [])
    risks = []
    if not customer.get("found"):
        risks.append("主体资格和客户资料未在演示 CRM 中完整找到")
    risks.extend(["现金流、负债与还款来源缺少可验证材料", "担保或增信安排需要补充合同和权属依据"])
    if not context:
        risks.append("缺少知识库依据")
    return "风险提示：" + "；".join(risks) + "。建议补充材料并提交人工复核。"


def _fast_compliance_review(context: list[dict[str, Any]]) -> str:
    if not context:
        return "未找到可引用合规依据，不能形成合规结论；请补充制度材料并人工复核。"
    sources = "、".join(sorted({str(item.get("source", "未知来源")) for item in context}))
    return f"已对照检索片段进行辅助审查，依据来源：{sources}。检索结果不等于最终合规结论，需人工复核。"


def build_graph(llm: Any | None = None, knowledge_base_dir: str | None = None):
    """Build and compile the supervisor -> specialist -> report graph."""
    model = llm or get_llm()
    skill_registry = get_skill_registry()
    gateway = ToolGateway()
    mode = execution_mode()

    def supervisor(state: FinancialState) -> dict[str, Any]:
        query = state["user_query"]
        task_type = _supervisor_task(model, query)
        selected_skills = skill_registry.recommend(query)
        return {
            "task_type": task_type,
            "selected_skills": selected_skills,
            "skill_context": skill_registry.render_context(selected_skills),
            "prompt_version": PROMPT_VERSION,
            "execution_mode": mode,
            "runtime": runtime_info(),
            "trace": state.get("trace", []) + ["supervisor"],
        }

    def data_collector(state: FinancialState) -> dict[str, Any]:
        query = state["user_query"]
        customer_name = extract_customer_name(query)
        customer = gateway.call("crm.query_customer", customer_name=customer_name) if customer_name else {
            "found": False,
            "error": "问题未提供客户名称",
            "source": "local_demo_crm",
        }
        customer_status = _customer_data_status(customer, customer_name)
        context = gateway.call(
            "knowledge.retrieve",
            query=query,
            directory=knowledge_base_dir,
        ) if state.get("task_type") in {"compliance_query", "due_diligence"} else []
        industry = customer.get("data", {}).get("industry", "通用") if customer.get("found") else "通用"
        news = gateway.call("industry.search_news", industry=industry, keywords=query) \
            if state.get("task_type") == "due_diligence" and customer.get("found") else {}
        collected_data = {"customer": customer, "customer_data_status": customer_status}
        financial_values = extract_financial_values(query)
        if financial_values:
            collected_data["financial_inputs"] = financial_values
            collected_data["financial_ratios"] = gateway.call(
                "finance.calculate_ratios", **financial_values
            )
        if not customer.get("found"):
            collection_note = "客户未在本地演示 CRM 中找到；系统不会补写客户事实，当前状态为资料待补充。"
        elif mode == "fast":
            collection_note = _fast_collection_note(customer, news, context)
        else:
            try:
                collection_note = _ask(
                    model,
                    f"{DATA_COLLECTOR_PROMPT}\n\n适用 Skill：\n{state.get('skill_context', '')}",
                    json.dumps({"customer": customer, "news": news, "sources": context}, ensure_ascii=False),
                )
            except Exception as exc:  # noqa: BLE001 - graph must return a user-safe fallback
                collection_note = f"数据采集摘要生成失败：{exc}"
        collected_data["collection_note"] = collection_note
        return {
            "customer_name": customer_name,
            "customer_data_status": customer_status,
            "collected_data": collected_data,
            "industry_news": news,
            "retrieved_context": context,
            "tool_trace": gateway.audit_log.copy(),
            "trace": state.get("trace", []) + ["data_collector"],
        }

    def risk_analyzer(state: FinancialState) -> dict[str, Any]:
        if state.get("task_type") != "due_diligence":
            return {"risk_analysis": {"status": "not_applicable"}, "trace": state.get("trace", []) + ["risk_analyzer"]}
        evidence = json.dumps({
            "collected_data": state.get("collected_data", {}),
            "industry_news": state.get("industry_news", {}),
        }, ensure_ascii=False)
        if mode == "fast":
            answer = _fast_risk_analysis(state)
        else:
            try:
                answer = _ask(
                    model,
                    f"{RISK_PROMPT}\n\n适用 Skill：\n{state.get('skill_context', '')}",
                    f"用户问题：{state['user_query']}\n已采集数据：{evidence}",
                )
            except Exception as exc:  # noqa: BLE001 - graph must return a user-safe fallback
                answer = f"风险分析模型调用失败：{exc}"
        return {
            "risk_analysis": {"analysis": answer, "evidence": state.get("collected_data", {})},
            "trace": state.get("trace", []) + ["risk_analyzer"],
        }

    def compliance_checker(state: FinancialState) -> dict[str, Any]:
        context = state.get("retrieved_context", [])
        if state.get("task_type") not in {"compliance_query", "due_diligence"}:
            result = {"status": "not_applicable"}
        elif not context:
            result = {"status": "no_evidence", "message": "知识库未找到相关依据，需要补充资料并人工复核"}
        else:
            evidence = "\n\n".join(f"来源：{item['source']}\n{item['snippet']}" for item in context)
            if mode == "fast":
                answer = _fast_compliance_review(context)
            else:
                try:
                    answer = _ask(
                        model,
                        f"{COMPLIANCE_PROMPT}\n\n适用 Skill：\n{state.get('skill_context', '')}",
                        f"问题：{state['user_query']}\n检索片段：{evidence}",
                    )
                except Exception as exc:  # noqa: BLE001 - graph must return a user-safe fallback
                    answer = f"合规审查模型调用失败：{exc}"
            result = {"status": "reviewed_against_retrieved_text", "analysis": answer, "sources": context}
        return {"compliance_review": result, "trace": state.get("trace", []) + ["compliance_checker"]}

    def report_writer(state: FinancialState) -> dict[str, Any]:
        task_type = state.get("task_type", "general_chat")
        ratios = state.get("collected_data", {}).get("financial_ratios")
        customer_status = state.get("customer_data_status", {})
        customer_missing = task_type == "due_diligence" and customer_status.get("status") == "not_found"
        high_risk = task_type in {"due_diligence", "compliance_query", "investment_query"}
        if customer_missing:
            report = _missing_customer_report(state)
        elif task_type == "investment_query":
            report = "我不能提供个股买卖、投资组合或个性化投资推荐。可以帮助你建立信息核查框架；本回答不构成投资建议，相关事项需人工复核。"
        elif ratios and mode == "fast":
            report = _format_ratio_report(state.get("collected_data", {}))
        elif task_type == "general_chat":
            general_input = state["user_query"]
            if ratios:
                general_input = json.dumps({
                    "query": state["user_query"],
                    "financial_inputs": state.get("collected_data", {}).get("financial_inputs", {}),
                    "financial_ratios": ratios,
                }, ensure_ascii=False)
            try:
                report = _ask(
                    model,
                    f"{REPORT_PROMPT}\n\n适用 Skill：\n{state.get('skill_context', '')}",
                    general_input,
                )
            except Exception as exc:  # noqa: BLE001 - graph must return a user-safe fallback
                report = f"模型调用失败：{exc}"
        else:
            payload = json.dumps({
                "query": state["user_query"],
                "collected_data": state.get("collected_data", {}),
                "retrieved_context": state.get("retrieved_context", []),
                "risk_analysis": state.get("risk_analysis", {}),
                "compliance_review": state.get("compliance_review", {}),
                "industry_news": state.get("industry_news", {}),
                "selected_skills": state.get("selected_skills", []),
            }, ensure_ascii=False)[:14000]
            try:
                report = _ask(
                    model,
                    f"{REPORT_PROMPT}\n\n适用 Skill：\n{state.get('skill_context', '')}",
                    payload,
                )
            except Exception as exc:  # noqa: BLE001 - graph must return a user-safe fallback
                report = f"报告生成模型调用失败：{exc}"
        if high_risk and "人工复核" not in report:
            report += "\n\n⚠️ 该问题涉及高风险金融事项，结果仅供辅助分析，需人工复核。"
        return {
            "final_report": report,
            "confidence": 0.2 if customer_missing else (0.75 if not high_risk else 0.55),
            "need_human_review": high_risk,
            "prompt_version": state.get("prompt_version", PROMPT_VERSION),
            "execution_mode": mode,
            "runtime": runtime_info(),
            "messages": [{"role": "user", "content": state["user_query"]}, {"role": "assistant", "content": report}],
            "trace": state.get("trace", []) + ["report_writer"],
        }

    builder = StateGraph(FinancialState)
    builder.add_node("supervisor", supervisor)
    builder.add_node("data_collector", data_collector)
    builder.add_node("risk_analyzer", risk_analyzer)
    builder.add_node("compliance_checker", compliance_checker)
    builder.add_node("report_writer", report_writer)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "data_collector")
    builder.add_edge("data_collector", "risk_analyzer")
    builder.add_edge("risk_analyzer", "compliance_checker")
    builder.add_edge("compliance_checker", "report_writer")
    builder.add_edge("report_writer", END)
    return builder.compile()


def invoke_graph(query: str, *, llm: Any | None = None, knowledge_base_dir: str | None = None) -> FinancialState:
    graph = build_graph(llm=llm, knowledge_base_dir=knowledge_base_dir)
    return graph.invoke({"user_query": query, "messages": [], "trace": []})


def _format_ratio_report(collected_data: dict[str, Any]) -> str:
    inputs = collected_data.get("financial_inputs", {})
    ratios = collected_data.get("financial_ratios", {})
    lines = ["已使用财务指标工具完成透明计算。", f"输入数据（万元）：{inputs}"]
    if ratios.get("error"):
        lines.append(f"计算结果：{ratios['error']}")
    else:
        if "profit_margin" in ratios:
            lines.append(f"利润率 = 利润 ÷ 收入 = {ratios['profit_margin']:.2%}")
        if "debt_to_revenue" in ratios:
            lines.append(f"债务收入比 = 负债 ÷ 收入 = {ratios['debt_to_revenue']:.2%}")
    lines.extend([
        "口径限制：数据来自用户输入，未核验币种、期间、审计状态和数据来源。",
        "该指标仅供辅助分析，不构成授信、投资或合规结论。",
    ])
    return "\n".join(lines)
