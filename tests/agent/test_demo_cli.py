from agent import AgentOrchestrator
from scripts.run_agent_demo import build_output, update_conversation_context


def test_demo_output_contains_all_acceptance_fields():
    state = AgentOrchestrator().run("南京客户数量")
    output = build_output(state)
    assert list(output) == [
        "user_query",
        "final_status",
        "grounded_conditions",
        "retrieved_metrics",
        "retrieved_dimensions",
        "retrieved_concepts",
        "resolved_entities",
        "query_plan",
        "validation_result",
        "clarification",
        "repair_count",
        "trace",
    ]
    assert output["user_query"] == "南京客户数量"
    assert output["validation_result"]["valid"] is True


def test_demo_context_keeps_previous_plan_for_follow_up():
    orchestrator = AgentOrchestrator()
    context = {}
    first = orchestrator.run("南京客户数量", context)
    update_conversation_context(context, first)
    second = orchestrator.run("改为苏州", context)
    assert second.query_plan["metrics"] == ["customer_count"]
    assert any(
        item.get("target") == "city" and item.get("value") == "苏州"
        for item in second.query_plan["filters"]
    )
