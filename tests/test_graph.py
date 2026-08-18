from langchain_core.messages import AIMessage

from src.graph import invoke_graph
from src.skills.registry import get_skill_registry


def test_demo_graph_runs_end_to_end():
    result = invoke_graph("什么是反洗钱？")
    assert result["task_type"] == "compliance_query"
    assert result["trace"] == [
        "supervisor",
        "data_collector",
        "risk_analyzer",
        "compliance_checker",
        "report_writer",
    ]
    assert result["final_report"]
    assert result["need_human_review"] is True


def test_investment_boundary_is_safe():
    result = invoke_graph("请推荐一只股票")
    assert result["task_type"] == "investment_query"
    assert "不构成投资建议" in result["final_report"]
    assert result["need_human_review"] is True


def test_investment_portfolio_boundary_is_safe():
    result = invoke_graph("请给我一个投资组合")
    assert result["task_type"] == "investment_query"
    assert result["need_human_review"] is True
    assert "不构成投资建议" in result["final_report"]


def test_customer_tool_does_not_invent_unknown_customer():
    result = invoke_graph("请对不存在的星河有限公司做尽调")
    assert result["task_type"] == "due_diligence"
    assert result["collected_data"]["customer"]["found"] is False
    status = result["customer_data_status"]
    assert status["status"] == "not_found"
    assert status["label"] == "资料待补充"
    assert status["can_form_lending_conclusion"] is False
    assert len(status["missing_materials"]) >= 4
    assert "不能据此形成确定性的授信" in result["final_report"]
    assert result["confidence"] == 0.2


def test_demo_customer_name_is_normalized():
    result = invoke_graph("请对示例科技有限公司做一份授信尽调")
    assert result["collected_data"]["customer"]["found"] is True
    assert result["customer_name"] == "示例科技有限公司"


def test_skills_are_loaded_and_routed():
    registry = get_skill_registry()
    assert len(registry.all()) >= 3
    names = registry.recommend("请对企业做授信尽调并分析财务风险")
    assert "customer_due_diligence" in names
    assert "financial_ratio_analysis" in names
    result = invoke_graph("请对示例科技有限公司做授信尽调")
    assert "customer_due_diligence" in result["selected_skills"]
    assert result["skill_context"]


def test_financial_ratio_skill_calls_tool_and_returns_transparent_result():
    result = invoke_graph("收入5000利润500，计算利润率")
    assert result["task_type"] == "general_chat"
    assert result["collected_data"]["financial_ratios"]["profit_margin"] == 0.1
    assert any(item["tool"] == "finance.calculate_ratios" for item in result["tool_trace"])
    assert "利润率" in result["final_report"]


def test_full_mode_invokes_supervisor_prompt_for_due_diligence(monkeypatch):
    monkeypatch.setenv("AGENT_EXECUTION_MODE", "full")

    class RecordingLLM:
        def __init__(self):
            self.system_prompts = []

        def invoke(self, messages):
            self.system_prompts.append(str(messages[0].content))
            if "任务主管" in self.system_prompts[-1]:
                return AIMessage(content='{"task_type":"due_diligence","reason":"授信尽调"}')
            return AIMessage(content="模型辅助结果")

    model = RecordingLLM()
    result = invoke_graph("请对示例科技有限公司做授信尽调", llm=model)
    assert result["task_type"] == "due_diligence"
    assert any("任务主管" in prompt for prompt in model.system_prompts)
