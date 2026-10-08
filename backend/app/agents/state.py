import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class AgentStepTrace:
    step_number: int
    action: str
    input_summary: str
    result_summary: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    step_cost: float
    cumulative_cost: float
    details: Optional[Dict[str, Any]] = None
    raw_args: Optional[Dict[str, Any]] = None
    is_tool_choice_valid: bool = True
    is_argument_valid: bool = True
    argument_error_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "input_summary": self.input_summary,
            "result_summary": self.result_summary,
            "latency_ms": round(self.latency_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "step_cost": round(self.step_cost, 6),
            "cumulative_cost": round(self.cumulative_cost, 6),
            "raw_args": self.raw_args or {},
            "is_tool_choice_valid": self.is_tool_choice_valid,
            "is_argument_valid": self.is_argument_valid,
            "argument_error_reason": self.argument_error_reason,
            "details": self.details or {}
        }


@dataclass
class AgentState:
    question: str
    document_id: Optional[str] = None
    doc_ids: Optional[List[str]] = None
    retrieved_evidence: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    mcp_results: List[Dict[str, Any]] = field(default_factory=list)  # calls to external MCP server tools
    iteration_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    start_time: float = field(default_factory=time.time)
    elapsed_seconds: float = 0.0
    termination_reason: str = "running"
    completed: bool = False
    final_answer: str = ""
    used_fallback: bool = False
    trace: List[AgentStepTrace] = field(default_factory=list)

    def record_step(
        self,
        action: str,
        input_summary: str,
        result_summary: str,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        step_cost: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
        raw_args: Optional[Dict[str, Any]] = None,
        is_tool_choice_valid: bool = True,
        is_argument_valid: bool = True,
        argument_error_reason: str = ""
    ) -> AgentStepTrace:
        self.iteration_count += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += (input_tokens + output_tokens)
        self.estimated_cost += step_cost
        self.elapsed_seconds = time.time() - self.start_time

        step_trace = AgentStepTrace(
            step_number=self.iteration_count,
            action=action,
            input_summary=input_summary,
            result_summary=result_summary,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            step_cost=step_cost,
            cumulative_cost=self.estimated_cost,
            details=details,
            raw_args=raw_args,
            is_tool_choice_valid=is_tool_choice_valid,
            is_argument_valid=is_argument_valid,
            argument_error_reason=argument_error_reason
        )
        self.trace.append(step_trace)
        return step_trace

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "document_id": self.document_id,
            "doc_ids": self.doc_ids,
            "iteration_count": self.iteration_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": round(self.estimated_cost, 6),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "termination_reason": self.termination_reason,
            "completed": self.completed,
            "final_answer": self.final_answer,
            "used_fallback": self.used_fallback,
            "retrieved_evidence_count": len(self.retrieved_evidence),
            "trace": [t.to_dict() for t in self.trace]
        }

