import json
import time
from typing import Optional, Dict, Any
from app.agents.state import AgentState
from app.agents.budgets import AgentBudgets
from app.agents.logger import AgentExecutionLogger
from app.agents.tools import (
    REGISTERED_TOOLS,
    EXPOSED_TOOL_FUNCTIONS,
    search_document,
    estimate_tokens,
)
from app.services import llm_service
from app.services.llm.client import ToolChat
from app.schemas.chat import SourceCitation

# Gemini pricing defaults ($0.075 / 1M input, $0.30 / 1M output)
MODEL_INPUT_COST_PER_1M = 0.075
MODEL_OUTPUT_COST_PER_1M = 0.30


def calculate_llm_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * MODEL_INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * MODEL_OUTPUT_COST_PER_1M
    return input_cost + output_cost


def _compact_for_llm(tool_result: Any) -> Any:
    """Drop the 300-char snippet from search results before sending them to the LLM; it also gets full_content."""
    if isinstance(tool_result, dict) and isinstance(tool_result.get("results"), list):
        return {**tool_result, "results": [{k: v for k, v in r.items() if k != "snippet"} for r in tool_result["results"]]}
    return tool_result


class AdaptiveRAGAgent:
    def __init__(self, budgets: Optional[AgentBudgets] = None, logger: Optional[AgentExecutionLogger] = None):
        self.budgets = budgets or AgentBudgets()
        self.logger = logger or AgentExecutionLogger()

    def run(
        self,
        question: str,
        document_id: Optional[str] = None,
        question_id: str = "q_adaptive",
        api_key: Optional[str] = None,
        top_k: int = 4
    ) -> AgentState:
        state = AgentState(question=question, document_id=document_id)

        accumulated_chunks: Dict[str, Dict[str, Any]] = {}

        # LLM function-calling orchestration. An LLM is required: errors propagate as LLMUnavailableError
        system_instruction = (
            "You are an expert autonomous RAG research agent. "
            "Injected Tools Available:\n"
            "1. semantic_vector_search: Dense vector retrieval for conceptual queries.\n"
            "2. exact_keyword_search: BM25 sparse keyword retrieval for specific terms, codes, or names.\n"
            "3. python_calculator: Deterministic math calculation.\n"
            "4. summarize_context: Summarize passages.\n"
            "5. validate_evidence: Evaluate context completeness.\n"
            "Use tools as needed to answer the user question. Call tools iteratively until sufficient evidence is found, then provide your complete final answer."
        )

        chat = ToolChat(
            system=system_instruction,
            user=f"Question: {question}\nDocument ID filter: {document_id or 'All'}",
            tools=EXPOSED_TOOL_FUNCTIONS,
            api_key=api_key,
        )

        while True:
            # 1. Budget enforcement before each step
            is_exceeded, reason = self.budgets.check_budgets(state)
            if is_exceeded and reason:
                state.termination_reason = reason
                state.completed = False
                self.logger.log_termination(
                    question_id=question_id,
                    reason=reason,
                    total_steps=state.iteration_count,
                    total_cost=state.estimated_cost,
                    total_tokens=state.total_tokens
                )
                self._generate_final_answer(state, accumulated_chunks, api_key)
                return state

            start_t = time.time()
            in_tok = estimate_tokens(str(chat.history))
            tool_calls, final_text = chat.step()
            latency_ms = (time.time() - start_t) * 1000

            # Calculate LLM usage
            out_tok = estimate_tokens(final_text or str([(c.name, c.args) for c in tool_calls]))
            step_cost = calculate_llm_cost(in_tok, out_tok)

            if tool_calls:
                # LLM requested tool execution
                for call in tool_calls:
                    fn_name = call.name
                    fn_args = dict(call.args)
                    tool_fn = REGISTERED_TOOLS.get(fn_name)

                    # Run tool; a bad call (unknown tool or arguments) is reported back to the model to correct
                    tool_start = time.time()
                    if tool_fn is None:
                        tool_result = {"error": f"Unknown tool '{fn_name}'. Available: {', '.join(REGISTERED_TOOLS)}"}
                    else:
                        # Inject document_id if not present in LLM args
                        if "document_id" in tool_fn.__code__.co_varnames and "document_id" not in fn_args:
                            fn_args["document_id"] = document_id
                        try:
                            tool_result = tool_fn(**fn_args)
                        except TypeError as err:
                            tool_result = {"error": f"Invalid arguments for '{fn_name}': {err}"}
                    tool_latency = (time.time() - tool_start) * 1000

                    # Collect evidence chunks if returned by tool
                    if isinstance(tool_result, dict) and "results" in tool_result:
                        for chunk in tool_result["results"]:
                            ckey = f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"
                            accumulated_chunks[ckey] = chunk
                        state.retrieved_evidence = list(accumulated_chunks.values())

                    # Record step
                    state.record_step(
                        action=f"tool_call:{fn_name}",
                        input_summary=json.dumps(fn_args),
                        result_summary=f"keys={list(tool_result.keys()) if isinstance(tool_result, dict) else 'non-dict'}",
                        latency_ms=latency_ms + tool_latency,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        step_cost=step_cost,
                        raw_args=fn_args
                    )
                    self.logger.log_step(
                        question_id=question_id,
                        step=state.iteration_count,
                        action=f"tool_call:{fn_name}",
                        safe_input_summary=f"args={fn_args}",
                        result_summary=f"tool={fn_name}",
                        latency_ms=latency_ms + tool_latency,
                        tokens=in_tok + out_tok,
                        cost=step_cost
                    )

                    # Report the tool result back to the LLM conversation
                    chat.add_tool_result(call, _compact_for_llm(tool_result))

            else:
                # LLM reached final text response
                state.final_answer = final_text
                state.completed = True
                state.termination_reason = "completed"

                state.record_step(
                    action="llm_final_answer",
                    input_summary=f"history_len={len(chat.history)}",
                    result_summary=f"answer_length={len(final_text)}",
                    latency_ms=latency_ms,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    step_cost=step_cost,
                    raw_args={"question": question}
                )
                self.logger.log_termination(
                    question_id=question_id,
                    reason="completed",
                    total_steps=state.iteration_count,
                    total_cost=state.estimated_cost,
                    total_tokens=state.total_tokens
                )
                return state

    def _generate_final_answer(
        self,
        state: AgentState,
        accumulated_chunks: Dict[str, Dict[str, Any]],
        api_key: Optional[str]
    ):
        start_t = time.time()

        # A budget can run out before any search ran (e.g. while Gemini was rate-limited);
        # never answer without looking at the documents at least once
        if not accumulated_chunks:
            res = search_document(query=state.question, document_id=state.document_id)
            for chunk in res.get("results", []):
                accumulated_chunks[f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"] = chunk
            state.retrieved_evidence = list(accumulated_chunks.values())

        citations = []
        for c in accumulated_chunks.values():
            citations.append(
                SourceCitation(
                    content=c.get("full_content", c.get("snippet", "")),
                    doc_id=c.get("doc_id", ""),
                    filename=c.get("filename", "Unknown"),
                    chunk_index=c.get("chunk_index", 0),
                    score=c.get("score", 1.0)
                )
            )

        chat_res = llm_service.generate_answer(
            question=state.question,
            sources=citations,
            api_key=api_key
        )
        latency_ms = (time.time() - start_t) * 1000

        state.final_answer = chat_res.answer
        state.used_fallback = chat_res.used_fallback

        in_tok = estimate_tokens(state.question + "".join([c.content for c in citations]))
        out_tok = estimate_tokens(chat_res.answer)
        cost = calculate_llm_cost(in_tok, out_tok)

        state.record_step(
            action="generate_answer",
            input_summary=f"citations_count={len(citations)}",
            result_summary=f"answer_length={len(chat_res.answer)} fallback={chat_res.used_fallback}",
            latency_ms=latency_ms,
            input_tokens=in_tok,
            output_tokens=out_tok,
            step_cost=cost,
            raw_args={"question": state.question, "sources_count": len(citations)}
        )
        self.logger.log_step(
            question_id="final",
            step=state.iteration_count,
            action="generate_answer",
            safe_input_summary=f"citations={len(citations)}",
            result_summary=f"answer_length={len(chat_res.answer)}",
            latency_ms=latency_ms,
            tokens=in_tok + out_tok,
            cost=cost
        )

