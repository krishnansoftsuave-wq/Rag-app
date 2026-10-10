from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    McpToolResult,
    SourceCitation,
    SystemExecutionResult,
    ComparisonMetrics
)
from app.services import hybrid_retriever_service, llm_service
from app.agents.rag_agent import AdaptiveRAGAgent
from app.agents.team.team_agent import TeamRAGAgent
from app.workflows.fixed_rag_workflow import FixedRAGWorkflow
from app.agents.state import AgentState
from app.services.llm.client import track_usage
from app.services.llm.prompts import PROMPT_VERSION
from app.core.security import decode_access_token, security_bearer
from app.core.tracing import classify_input, start_trace
from app.services.retrieval.version_policy import question_scope

router = APIRouter()
agent_service = AdaptiveRAGAgent()
team_service = TeamRAGAgent()  # manager + concepts / reference specialists (Week 10)
workflow_service = FixedRAGWorkflow()


def _state_to_system_result(system_name: str, state: AgentState) -> SystemExecutionResult:
    citations = []
    for c in state.retrieved_evidence:
        citations.append(
            SourceCitation(
                content=c.get("full_content", c.get("snippet", "")),
                doc_id=c.get("doc_id", ""),
                filename=c.get("filename", "Unknown"),
                chunk_index=c.get("chunk_index", 0),
                score=c.get("score", 1.0)
            )
        )
    return SystemExecutionResult(
        system=system_name,
        answer=state.final_answer or "No response generated.",
        latency_ms=round(state.elapsed_seconds * 1000, 2),
        total_tokens=state.total_tokens,
        cost=round(state.estimated_cost, 6),
        iterations=state.iteration_count,
        termination_reason=state.termination_reason,
        sources=citations,
        used_fallback=state.used_fallback,
        trace=[t.to_dict() for t in state.trace],
        mcp_results=[McpToolResult(**r) for r in state.mcp_results]
    )


def _run_measured(system_name: str, service, question: str, doc_id) -> tuple:
    """Run the single agent or the team and report the provider-reported tokens and cost of every LLM call it
    made (the single agent's own counters are estimates), so their answers can be compared fairly."""
    with track_usage() as meter:
        state = service.run(question=question, document_id=doc_id)
    result = _state_to_system_result(system_name, state)
    result.total_tokens = meter.total_tokens
    result.cost = round(meter.cost, 6)
    result.llm_calls = len(meter.calls)
    result.models = meter.models
    return state, result


def _compute_comparison(agent_res: SystemExecutionResult, workflow_res: SystemExecutionResult) -> ComparisonMetrics:
    # Latency winner
    if abs(agent_res.latency_ms - workflow_res.latency_ms) < 50:
        lat_winner = "tie"
    elif agent_res.latency_ms < workflow_res.latency_ms:
        lat_winner = "agent"
    else:
        lat_winner = "workflow"

    # Token winner
    if agent_res.total_tokens == workflow_res.total_tokens:
        tok_winner = "tie"
    elif agent_res.total_tokens < workflow_res.total_tokens:
        tok_winner = "agent"
    else:
        tok_winner = "workflow"

    # Cost winner
    if abs(agent_res.cost - workflow_res.cost) < 0.000001:
        cost_winner = "tie"
    elif agent_res.cost < workflow_res.cost:
        cost_winner = "agent"
    else:
        cost_winner = "workflow"

    # Accuracy / Relevance winner
    if agent_res.termination_reason == "completed" and workflow_res.termination_reason == "completed":
        if len(agent_res.sources) >= len(workflow_res.sources) and agent_res.iterations <= workflow_res.iterations:
            acc_winner = "agent"
        else:
            acc_winner = "workflow"
    elif agent_res.termination_reason == "completed":
        acc_winner = "agent"
    elif workflow_res.termination_reason == "completed":
        acc_winner = "workflow"
    else:
        acc_winner = "tie"

    wins = {"agent": 0, "workflow": 0, "tie": 0}
    wins[lat_winner] += 1
    wins[tok_winner] += 1
    wins[cost_winner] += 1
    wins[acc_winner] += 1

    if wins["agent"] > wins["workflow"]:
        verdict = f"Adaptive Agent outperforms Fixed Workflow! It achieved higher efficiency with dynamic evidence validation."
    elif wins["workflow"] > wins["agent"]:
        verdict = f"Fixed Workflow outperforms Adaptive Agent! Its static execution pipeline had lower overall overhead."
    else:
        verdict = "Tie! Both systems achieved equivalent performance, token efficiency, and response accuracy."

    return ComparisonMetrics(
        latency_winner=lat_winner,
        tokens_winner=tok_winner,
        cost_winner=cost_winner,
        accuracy_winner=acc_winner,
        summary_verdict=verdict
    )


def _caller(credentials: Optional[HTTPAuthorizationCredentials], request: ChatRequest) -> Dict[str, Any]:
    """Who asked, for the trace: the signed-in user if the token is valid, else the id the client sent, else anonymous.
    /chat stays open to guests, so a bad token is logged rather than rejected."""
    if credentials and credentials.credentials:
        try:
            payload = decode_access_token(credentials.credentials)
            return {"user_id": payload.get("sub") or "unknown", "username": payload.get("username")}
        except HTTPException:
            return {"user_id": request.user_id or "invalid_token", "username": None}
    return {"user_id": request.user_id or "anonymous", "username": None}


# Plain `def` so FastAPI runs the blocking agent/LLM calls in a worker thread instead of freezing the event loop
@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    mode = (request.mode or "agent").lower()
    # One trace record per request (logs/requests.jsonl): who asked what, which chunks were retrieved, what was
    # answered, and the latency, tokens and cost of every step
    with start_trace(
        mode=mode,
        **_caller(credentials, request),
        session_id=request.session_id,
        prompt_version=PROMPT_VERSION,
        query=request.question,
        input_type=classify_input(request.question),
        doc_ids=request.doc_ids,
        search_mode=request.search_mode,
    ) as trace:
        with question_scope(request.question):
            result = _answer(request, mode)
        systems = {r.system: r for r in (result.agent_result, result.team_result, result.workflow_result) if r}
        primary = systems.get(mode)
        trace.set(
            answer=result.answer,
            termination_reason=primary.termination_reason if primary else None,
            system_answers={name: r.answer for name, r in systems.items()} if len(systems) > 1 else None,
        )
    result.trace_id = trace.trace_id
    response.headers["X-Trace-Id"] = trace.trace_id
    return result


def _answer(request: ChatRequest, mode: str) -> ChatResponse:
    doc_id = request.doc_ids[0] if request.doc_ids else None

    if mode == "agent":
        _, agent_res = _run_measured("agent", agent_service, request.question, doc_id)
        return ChatResponse(
            question=request.question,
            answer=agent_res.answer,
            sources=agent_res.sources,
            used_fallback=agent_res.used_fallback,
            mode="agent",
            agent_result=agent_res,
            mcp_results=agent_res.mcp_results
        )

    elif mode == "team":
        _, team_res = _run_measured("team", team_service, request.question, doc_id)
        return ChatResponse(
            question=request.question,
            answer=team_res.answer,
            sources=team_res.sources,
            used_fallback=team_res.used_fallback,
            mode="team",
            team_result=team_res
        )

    elif mode == "workflow":
        workflow_state = workflow_service.run(question=request.question, document_id=doc_id)
        workflow_res = _state_to_system_result("workflow", workflow_state)
        return ChatResponse(
            question=request.question,
            answer=workflow_res.answer,
            sources=workflow_res.sources,
            used_fallback=workflow_res.used_fallback,
            mode="workflow",
            workflow_result=workflow_res
        )

    elif mode == "standard":
        sources = hybrid_retriever_service.retrieve_context(
            query=request.question,
            doc_ids=request.doc_ids,
            search_mode=request.search_mode or "hybrid"
        )
        response = llm_service.generate_answer(
            question=request.question,
            sources=sources,
            provider=request.provider or "gemini"
        )
        return ChatResponse(
            question=request.question,
            answer=response.answer,
            sources=response.sources,
            used_fallback=response.used_fallback,
            mode="standard"
        )

    # Default mode == "compare"
    agent_state = agent_service.run(question=request.question, document_id=doc_id)
    workflow_state = workflow_service.run(question=request.question, document_id=doc_id)

    agent_res = _state_to_system_result("agent", agent_state)
    workflow_res = _state_to_system_result("workflow", workflow_state)
    comparison = _compute_comparison(agent_res, workflow_res)

    # Choose primary answer (agent if completed/better, else workflow)
    primary_answer = agent_res.answer if agent_state.completed else workflow_res.answer
    primary_sources = agent_res.sources if agent_state.completed else workflow_res.sources
    primary_fallback = agent_res.used_fallback and workflow_res.used_fallback

    return ChatResponse(
        question=request.question,
        answer=primary_answer,
        sources=primary_sources,
        used_fallback=primary_fallback,
        mode="compare",
        agent_result=agent_res,
        workflow_result=workflow_res,
        comparison=comparison,
        mcp_results=agent_res.mcp_results  # only the agent calls MCP tools
    )

