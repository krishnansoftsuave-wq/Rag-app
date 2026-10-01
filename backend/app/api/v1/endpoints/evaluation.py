import os
import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.agents.rag_agent import AdaptiveRAGAgent
from app.workflows.fixed_rag_workflow import FixedRAGWorkflow
from app.evaluation.benchmark import BenchmarkRunner, SUMMARY_JSON_PATH, RACE_CSV_PATH
from app.schemas.chat import ChatRequest

router = APIRouter()
agent_service = AdaptiveRAGAgent()
workflow_service = FixedRAGWorkflow()


@router.post("/agent/chat")
async def run_agent_chat(request: ChatRequest):
    """Run Adaptive RAG Agent on a user question."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    doc_id = request.doc_ids[0] if request.doc_ids else None
    state = agent_service.run(
        question=request.question,
        document_id=doc_id,
        api_key=request.api_key
    )
    return {
        "question": request.question,
        "answer": state.final_answer,
        "used_fallback": state.used_fallback,
        "state": state.to_dict()
    }


@router.post("/workflow/chat")
async def run_workflow_chat(request: ChatRequest):
    """Run Fixed RAG Workflow on a user question."""
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    doc_id = request.doc_ids[0] if request.doc_ids else None
    state = workflow_service.run(
        question=request.question,
        document_id=doc_id,
        api_key=request.api_key
    )
    return {
        "question": request.question,
        "answer": state.final_answer,
        "used_fallback": state.used_fallback,
        "state": state.to_dict()
    }


@router.post("/evaluation/run")
async def trigger_benchmark(
    background_tasks: BackgroundTasks,
    system: str = Query("both", description="System type: 'agent', 'workflow', or 'both'"),
    doc_id: Optional[str] = Query(None, description="Optional document ID filter")
):
    """Executes full 10-question benchmark suite."""
    try:
        runner = BenchmarkRunner()
        summary_data = runner.run_benchmark(system_type=system, document_id=doc_id)
        return {
            "message": "Benchmark completed successfully!",
            "summary": summary_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark execution failed: {str(e)}")


@router.get("/evaluation/results")
async def get_benchmark_results():
    """Retrieve benchmark summary and per-question results."""
    if not os.path.exists(SUMMARY_JSON_PATH):
        # Run benchmark automatically if not yet run
        runner = BenchmarkRunner()
        return runner.run_benchmark(system_type="both")

    with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/evaluation/questions/{question_id}")
async def get_question_benchmark_detail(question_id: str):
    """Retrieve detailed question performance metrics."""
    if not os.path.exists(SUMMARY_JSON_PATH):
        raise HTTPException(status_code=404, detail="Benchmark results not found. Run benchmark first.")

    with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ag_matches = [q for q in data.get("agent_question_results", []) if q["question_id"] == question_id]
    wf_matches = [q for q in data.get("workflow_question_results", []) if q["question_id"] == question_id]

    return {
        "question_id": question_id,
        "agent": ag_matches[0] if ag_matches else None,
        "workflow": wf_matches[0] if wf_matches else None
    }


@router.get("/evaluation/trace/{question_id}")
async def get_execution_trace(question_id: str):
    """Retrieve observable execution trace for both Agent and Fixed Workflow."""
    if not os.path.exists(SUMMARY_JSON_PATH):
        raise HTTPException(status_code=404, detail="Benchmark results not found. Run benchmark first.")

    with open(SUMMARY_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ag_matches = [q for q in data.get("agent_question_results", []) if q["question_id"] == question_id]
    wf_matches = [q for q in data.get("workflow_question_results", []) if q["question_id"] == question_id]

    return {
        "question_id": question_id,
        "agent_trace": ag_matches[0].get("trace", []) if ag_matches else [],
        "workflow_trace": wf_matches[0].get("trace", []) if wf_matches else []
    }
