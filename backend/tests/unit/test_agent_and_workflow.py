import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # backend/

from app.agents.tools import search_document, refine_document_search, validate_evidence
from app.agents.budgets import AgentBudgets
from app.agents.state import AgentState
from app.agents.rag_agent import AdaptiveRAGAgent
from app.workflows.fixed_rag_workflow import FixedRAGWorkflow
from app.evaluation.metrics import calculate_p50_latency, calculate_pass_rate, summarize_metrics
from app.evaluation.evaluator import evaluate_answer


def test_tools():
    print("Testing 3 RAG Tools...")
    # Tool 1: search_document
    s_res = search_document(document_id=None, query="test query", top_k=2)
    assert "results" in s_res
    assert "result_count" in s_res

    # Tool 2: refine_document_search
    r_res = refine_document_search(document_id=None, query="refined test query", top_k=2)
    assert "refined_query" in r_res

    # Tool 3: validate_evidence
    v_res = validate_evidence(question="What is DocuBrain?", retrieved_context="DocuBrain is an enterprise RAG application.")
    assert "sufficient" in v_res
    assert "reason" in v_res
    print("   Tools test PASSED.")


def test_budgets():
    print("Testing 4 Safety Budgets...")
    b = AgentBudgets(max_iterations=2, max_tokens=100, max_cost=0.01, max_wall_clock_seconds=0.1)
    
    # 1. Iterations
    s1 = AgentState(question="q")
    s1.iteration_count = 2
    ex, reason = b.check_budgets(s1)
    assert ex and reason == "max_iterations"

    # 2. Tokens
    s2 = AgentState(question="q")
    s2.total_tokens = 150
    ex, reason = b.check_budgets(s2)
    assert ex and reason == "max_tokens"

    # 3. Cost
    s3 = AgentState(question="q")
    s3.estimated_cost = 0.02
    ex, reason = b.check_budgets(s3)
    assert ex and reason == "max_cost"

    # 4. Wall clock
    s4 = AgentState(question="q")
    s4.start_time = time.time() - 0.5
    ex, reason = b.check_budgets(s4)
    assert ex and reason == "wall_clock"

    print("   Budgets test PASSED.")


def test_agent_and_workflow():
    print("Testing Adaptive Agent and Fixed Workflow execution...")
    agent = AdaptiveRAGAgent()
    wf = FixedRAGWorkflow()

    ag_state = agent.run("What is DocuBrain vector search?", question_id="test_ag")
    assert ag_state.iteration_count > 0
    assert ag_state.final_answer != ""

    wf_state = wf.run("What is DocuBrain vector search?", question_id="test_wf")
    assert wf_state.iteration_count == 4
    assert wf_state.final_answer != ""

    print("   Agent & Workflow execution test PASSED.")


def test_metrics():
    print("Testing metrics calculation...")
    p50 = calculate_p50_latency([100.0, 200.0, 300.0, 400.0, 500.0])
    assert p50 == 300.0

    pr = calculate_pass_rate([True, True, False, True])
    assert pr == 75.0

    print("   Metrics test PASSED.")


if __name__ == "__main__":
    test_tools()
    test_budgets()
    test_agent_and_workflow()
    test_metrics()
    print("All unit tests completed successfully!")
