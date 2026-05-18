from app.services.evaluator import AgentQualityEvaluator


def test_agent_quality_evaluator_methods():
    evaluator = AgentQualityEvaluator()
    plan = {
        "steps": [
            {"id": 1, "action": "retrieve_data", "depends_on": [], "tool_call": {"tool": "rag_search", "args": {}}},
            {"id": 2, "action": "answer", "depends_on": [1], "tool_call": {"tool": None, "args": {}}},
        ]
    }
    state = {
        "status": "done",
        "history": [
            {"transition_decision": "retry"},
            {"transition_decision": "advance"},
        ],
    }
    run_output = {"answer": "ok", "metadata": {"plan": plan, "final_state": state}}

    pq = evaluator.evaluate_plan_quality(plan)
    rq = evaluator.evaluate_reflection_trace(state)
    aq = evaluator.evaluate_agent_run(run_output)

    assert pq["plan_step_count"] == 2
    assert rq["reflection_triggered"] is True
    assert aq["answer_present"] is True
