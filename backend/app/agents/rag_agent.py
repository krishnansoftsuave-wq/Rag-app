import os
import json
import time
from typing import Optional, List, Dict, Any
from app.agents.state import AgentState
from app.agents.budgets import AgentBudgets
from app.agents.logger import AgentExecutionLogger
from app.agents.tools import (
    REGISTERED_TOOLS,
    EXPOSED_TOOL_FUNCTIONS,
    search_document,
    refine_document_search,
    validate_evidence,
    semantic_vector_search,
    exact_keyword_search,
    python_calculator,
    estimate_tokens,
)
from app.services import llm_service
from app.schemas.chat import SourceCitation
from app.core.config import GEMINI_API_KEY

# Gemini pricing defaults ($0.075 / 1M input, $0.30 / 1M output)
MODEL_INPUT_COST_PER_1M = 0.075
MODEL_OUTPUT_COST_PER_1M = 0.30


def calculate_llm_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * MODEL_INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * MODEL_OUTPUT_COST_PER_1M
    return input_cost + output_cost


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
        key_to_use = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

        accumulated_chunks: Dict[str, Dict[str, Any]] = {}
        last_missing_info: List[str] = []

        # Try dynamic LLM Function Calling orchestration if API key is available
        if key_to_use:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=key_to_use)
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

                contents = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=f"Question: {question}\nDocument ID filter: {document_id or 'All'}")]
                    )
                ]

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
                        self._generate_final_answer(state, accumulated_chunks, key_to_use)
                        return state

                    start_t = time.time()
                    model_response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            tools=EXPOSED_TOOL_FUNCTIONS,
                            temperature=0.2
                        )
                    )
                    latency_ms = (time.time() - start_t) * 1000

                    # Calculate LLM usage
                    in_tok = estimate_tokens(str(contents))
                    out_tok = estimate_tokens(str(model_response.text or model_response.function_calls or ""))
                    step_cost = calculate_llm_cost(in_tok, out_tok)

                    # Inspect tool calls
                    function_calls = getattr(model_response, "function_calls", None)

                    if function_calls:
                        # LLM requested tool execution
                        contents.append(model_response.candidates[0].content)

                        for call in function_calls:
                            fn_name = call.name
                            fn_args = dict(call.args) if call.args else {}

                            # Inject document_id if not present in LLM args
                            if "document_id" in REGISTERED_TOOLS[fn_name].__code__.co_varnames and "document_id" not in fn_args:
                                fn_args["document_id"] = document_id

                            # Run tool
                            tool_fn = REGISTERED_TOOLS.get(fn_name, search_document)
                            tool_start = time.time()
                            tool_result = tool_fn(**fn_args)
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

                            # Append tool response back to LLM conversation contents
                            contents.append(
                                types.Content(
                                    role="tool",
                                    parts=[
                                        types.Part.from_function_response(
                                            name=fn_name,
                                            response={"result": tool_result}
                                        )
                                    ]
                                )
                            )

                    else:
                        # LLM reached final text response
                        final_text = model_response.text or ""
                        state.final_answer = final_text
                        state.completed = True
                        state.termination_reason = "completed"

                        state.record_step(
                            action="llm_final_answer",
                            input_summary=f"history_len={len(contents)}",
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

            except Exception as err:
                # Fall through to local agent loop if API error occurs
                pass

        # Fallback Local Heuristic Loop (used offline or when API Key unavailable)
        current_query = question
        while True:
            # 1. Safety Budgets
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
                self._generate_final_answer(state, accumulated_chunks, key_to_use)
                break

            # 2. Decide Action
            if len(accumulated_chunks) == 0:
                action = "search_document"
            elif last_missing_info:
                action = "refine_document_search"
            else:
                action = "validate_evidence"

            start_t = time.time()

            if action == "search_document":
                res = search_document(query=current_query, document_id=document_id, top_k=top_k)
                latency_ms = (time.time() - start_t) * 1000

                for chunk in res["results"]:
                    chunk_key = f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"
                    accumulated_chunks[chunk_key] = chunk

                state.retrieved_evidence = list(accumulated_chunks.values())
                state.record_step(
                    action="search_document",
                    input_summary=f"query='{current_query}'",
                    result_summary=f"results={res['result_count']} top_score={res['top_score']}",
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=0,
                    step_cost=0.0,
                    raw_args={"document_id": document_id, "query": current_query, "top_k": top_k}
                )
                self.logger.log_step(
                    question_id=question_id,
                    step=state.iteration_count,
                    action="search_document",
                    safe_input_summary=f"query='{current_query}'",
                    result_summary=f"results={res['result_count']}",
                    latency_ms=latency_ms,
                    tokens=0,
                    cost=0.0
                )
                last_missing_info = []

            elif action == "refine_document_search":
                refined_query = f"{question} {last_missing_info[0]}" if last_missing_info else question
                res = refine_document_search(query=refined_query, document_id=document_id, top_k=top_k)
                latency_ms = (time.time() - start_t) * 1000

                for chunk in res["results"]:
                    chunk_key = f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"
                    accumulated_chunks[chunk_key] = chunk

                state.retrieved_evidence = list(accumulated_chunks.values())
                state.record_step(
                    action="refine_document_search",
                    input_summary=f"query='{refined_query}'",
                    result_summary=f"results={res['result_count']} top_score={res['top_score']}",
                    latency_ms=latency_ms,
                    input_tokens=0,
                    output_tokens=0,
                    step_cost=0.0,
                    raw_args={"document_id": document_id, "query": refined_query, "top_k": top_k}
                )
                self.logger.log_step(
                    question_id=question_id,
                    step=state.iteration_count,
                    action="refine_document_search",
                    safe_input_summary=f"query='{refined_query}'",
                    result_summary=f"results={res['result_count']}",
                    latency_ms=latency_ms,
                    tokens=0,
                    cost=0.0
                )
                last_missing_info = []

            elif action == "validate_evidence":
                combined_context = "\n\n".join([c["full_content"] for c in accumulated_chunks.values()])
                val_res = validate_evidence(question=question, retrieved_context=combined_context, api_key=key_to_use)
                latency_ms = (time.time() - start_t) * 1000

                in_tok = val_res.get("input_tokens", 0)
                out_tok = val_res.get("output_tokens", 0)
                step_cost = calculate_llm_cost(in_tok, out_tok)

                sufficient = val_res.get("sufficient", False)
                missing = val_res.get("missing_information", [])

                state.record_step(
                    action="validate_evidence",
                    input_summary=f"context_length={len(combined_context)}",
                    result_summary=f"sufficient={sufficient} missing_count={len(missing)}",
                    latency_ms=latency_ms,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    step_cost=step_cost,
                    raw_args={"question": question, "retrieved_context_len": len(combined_context)}
                )
                self.logger.log_step(
                    question_id=question_id,
                    step=state.iteration_count,
                    action="validate_evidence",
                    safe_input_summary=f"context_length={len(combined_context)}",
                    result_summary=f"sufficient={sufficient}",
                    latency_ms=latency_ms,
                    tokens=in_tok + out_tok,
                    cost=step_cost
                )

                if sufficient:
                    self._generate_final_answer(state, accumulated_chunks, key_to_use)
                    state.completed = True
                    state.termination_reason = "completed"
                    self.logger.log_termination(
                        question_id=question_id,
                        reason="completed",
                        total_steps=state.iteration_count,
                        total_cost=state.estimated_cost,
                        total_tokens=state.total_tokens
                    )
                    break
                else:
                    last_missing_info = missing if missing else [question]

        return state

    def _generate_final_answer(
        self,
        state: AgentState,
        accumulated_chunks: Dict[str, Dict[str, Any]],
        api_key: Optional[str]
    ):
        start_t = time.time()
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

