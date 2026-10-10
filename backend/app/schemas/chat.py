from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class SourceCitation(BaseModel):
    content: str
    doc_id: str
    filename: str
    chunk_index: int
    score: float


class ChatRequest(BaseModel):
    question: str
    doc_ids: Optional[List[str]] = None
    provider: Optional[str] = "gemini"  # "gemini", "openai", or "auto"
    search_mode: Optional[str] = "hybrid"  # "hybrid", "vector", or "bm25"
    mode: Optional[str] = "compare"  # "compare", "agent", "team", "workflow", or "standard"


class McpToolResult(BaseModel):
    """A call the agent made to a tool on an external MCP server. A result with "type" and "data" is an artifact."""
    server_id: str
    server_name: str
    tool_name: str
    arguments: Dict[str, Any] = {}  # as chosen by the model; backend-filled context parameters are not included
    success: bool
    result: Any = None
    error: Optional[str] = None


class SystemExecutionResult(BaseModel):
    system: str  # "agent", "team" or "workflow"
    answer: str
    latency_ms: float
    total_tokens: int
    cost: float
    iterations: int
    termination_reason: str
    sources: List[SourceCitation]
    used_fallback: bool
    trace: List[Dict[str, Any]] = []
    mcp_results: List[McpToolResult] = []
    llm_calls: int = 0  # provider-reported calls, when measured (agent and team modes)
    models: List[str] = []  # models that answered those calls; more than one means a call fell back


class ComparisonMetrics(BaseModel):
    latency_winner: str  # "agent", "workflow", or "tie"
    tokens_winner: str   # "agent", "workflow", or "tie"
    cost_winner: str     # "agent", "workflow", or "tie"
    accuracy_winner: str # "agent", "workflow", or "tie"
    summary_verdict: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceCitation]
    used_fallback: bool = False
    mode: str = "compare"
    agent_result: Optional[SystemExecutionResult] = None
    team_result: Optional[SystemExecutionResult] = None
    workflow_result: Optional[SystemExecutionResult] = None
    comparison: Optional[ComparisonMetrics] = None
    mcp_results: List[McpToolResult] = []

