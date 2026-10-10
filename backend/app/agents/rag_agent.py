import json
import time
from typing import Optional, Dict, Any
from app.services.retrieval.version_policy import question_scope
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
from app.services.llm.client import ToolChat, choose_tool_call
from app.services.retrieval.excerpts import focus_terms, focused_excerpt, prepare_sources
from app.mcp.client.agent_tools import (
    McpAgentTool,
    is_artifact,
    load_server_tools,
    run_agent_tool,
    select_mcp_server,
    summarize_for_llm,
)
from app.mcp.client.manager import mcp_client_manager
from app.schemas.chat import SourceCitation
from app.core.tracing import span
from app.services.llm.prompts import AGENT_SYSTEM_PROMPT, PROMPT_VERSION

# Tools whose work is retrieving chunks; their spans count toward the retrieval stage, other tools toward "tool"
RETRIEVAL_TOOLS = {"semantic_vector_search", "exact_keyword_search", "search_document", "refine_document_search"}

# Gemini pricing defaults ($0.075 / 1M input, $0.30 / 1M output)
MODEL_INPUT_COST_PER_1M = 0.075
MODEL_OUTPUT_COST_PER_1M = 0.30


def calculate_llm_cost(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1_000_000) * MODEL_INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * MODEL_OUTPUT_COST_PER_1M
    return input_cost + output_cost


MAX_RESULTS_FOR_LLM = 5
MAX_CHUNK_CHARS_FOR_LLM = 1000


def _compact_for_llm(tool_result: Any, terms: set) -> Any:
    """Search results as the LLM sees them: the top results only, no duplicate snippet, and long chunks reduced
    to their sentences relevant to the question, so the conversation stays within per-request token limits.
    (All retrieved chunks are still kept in full for the sources and the final answer.)"""
    if isinstance(tool_result, dict) and isinstance(tool_result.get("results"), list):
        compact = []
        for r in tool_result["results"][:MAX_RESULTS_FOR_LLM]:
            item = {k: v for k, v in r.items() if k != "snippet"}
            item["full_content"] = focused_excerpt(str(r.get("full_content", "")), terms, MAX_CHUNK_CHARS_FOR_LLM)
            compact.append(item)
        return {**tool_result, "results": compact}
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
        top_k: int = 4
    ) -> AgentState:
        # Archived docs are searched only if the question asks about an older version (retrieval/version_policy.py)
        with question_scope(question):
            return self._run(question, document_id, question_id, top_k)

    def _run(self, question: str, document_id: Optional[str], question_id: str, top_k: int) -> AgentState:
        state = AgentState(question=question, document_id=document_id)

        accumulated_chunks: Dict[str, Dict[str, Any]] = {}
        terms = focus_terms(question)

        # LLM function-calling orchestration. An LLM is required: errors propagate as LLMUnavailableError
        system_instruction = AGENT_SYSTEM_PROMPT

        # MCP stages 1-2: decide whether this request needs an external MCP server; only then connect and list its tools.
        # Stage 3 (_run_mcp_action) runs once the documents have been searched, so the tool gets the passages.
        mcp_tools: Dict[str, McpAgentTool] = {}
        server = self._select_mcp_server(state, question, question_id)
        if server:
            mcp_tools = self._load_mcp_tools(state, server, question_id)
        mcp_pending = bool(mcp_tools)
        if mcp_pending:
            system_instruction += (
                f"\nThe output this request asks for (for example a visual or structured view) is produced separately "
                f"by the MCP server '{server['name']}' and shown to the user. Focus on finding the facts in the documents "
                "and keep your final answer short; do not reproduce that output yourself."
            )

        chat = ToolChat(
            system=system_instruction,
            user=f"Question: {question}\nDocument ID filter: {document_id or 'All'}",
            tools=EXPOSED_TOOL_FUNCTIONS,
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
                if mcp_pending:
                    self._run_mcp_action(state, server, mcp_tools, accumulated_chunks, terms, question_id)
                self._generate_final_answer(state, accumulated_chunks)
                return state

            start_t = time.time()
            in_tok = estimate_tokens(str(chat.history))
            with span("agent_llm_step", stage="generation", step=state.iteration_count + 1,
                      prompt_version=PROMPT_VERSION) as llm_span:
                tool_calls, final_text = chat.step()
                if llm_span is not None:
                    llm_span.attrs["decision"] = [c.name for c in tool_calls] or "final_answer"
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
                    stage = "retrieval" if fn_name in RETRIEVAL_TOOLS else "tool"
                    with span(f"tool:{fn_name}", stage=stage, args=fn_args):
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
                    chat.add_tool_result(call, _compact_for_llm(tool_result, terms))

                # MCP stage 3 as soon as the documents have been searched; the model hears what it produced
                if mcp_pending and accumulated_chunks:
                    mcp_pending = False
                    note = self._run_mcp_action(state, server, mcp_tools, accumulated_chunks, terms, question_id)
                    if note:
                        chat.add_note(note)

            else:
                if mcp_pending:
                    mcp_pending = False
                    self._run_mcp_action(state, server, mcp_tools, accumulated_chunks, terms, question_id)
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

    def _select_mcp_server(
        self, state: AgentState, question: str, question_id: str
    ) -> Optional[Dict[str, Any]]:
        """Stage 1: the LLM sees only the enabled MCP servers' descriptions and picks one, or none."""
        if not mcp_client_manager.active_servers():
            return None
        start_t = time.time()
        with span("mcp_select_server", stage="tool"):
            server, reason = select_mcp_server(question)
        latency_ms = (time.time() - start_t) * 1000
        chosen = server["name"] if server else "none"
        state.record_step(
            action="mcp_select_server",
            input_summary=f"servers={len(mcp_client_manager.active_servers())}",
            result_summary=f"server={chosen} reason={reason}",
            latency_ms=latency_ms,
            raw_args={"question": question},
            details={"server_id": server["id"] if server else None, "reason": reason}
        )
        self.logger.log_step(
            question_id=question_id,
            step=state.iteration_count,
            action="mcp_select_server",
            safe_input_summary=f"servers={len(mcp_client_manager.active_servers())}",
            result_summary=f"server={chosen}",
            latency_ms=latency_ms,
            tokens=0,
            cost=0.0
        )
        return server

    def _load_mcp_tools(self, state: AgentState, server: Dict[str, Any], question_id: str) -> Dict[str, McpAgentTool]:
        """Stage 2: connect to the chosen server now and list its tools for the LLM."""
        start_t = time.time()
        with span("mcp_list_tools", stage="tool", server=server["name"]):
            tools, error = load_server_tools(server, reserved_names=set(REGISTERED_TOOLS))
        latency_ms = (time.time() - start_t) * 1000
        state.record_step(
            action="mcp_list_tools",
            input_summary=f"server={server['name']}",
            result_summary=f"tools={[t.tool_name for t in tools]}" if not error else f"error={error}",
            latency_ms=latency_ms,
            raw_args={"server_id": server["id"]},
            details={"tools": [t.tool_name for t in tools], "error": error}
        )
        self.logger.log_step(
            question_id=question_id,
            step=state.iteration_count,
            action="mcp_list_tools",
            safe_input_summary=f"server={server['name']}",
            result_summary=f"tools={len(tools)}" if not error else "connection failed",
            latency_ms=latency_ms,
            tokens=0,
            cost=0.0
        )
        if error:
            # Tell the user why the MCP output is missing; the answer still comes from the documents
            state.mcp_results.append({
                "server_id": server["id"], "server_name": server["name"], "tool_name": "list_tools",
                "arguments": {}, "success": False, "result": None,
                "error": f"Could not connect to the MCP server: {error}",
            })
        return {t.name: t for t in tools}

    def _run_mcp_action(
        self,
        state: AgentState,
        server: Dict[str, Any],
        mcp_tools: Dict[str, McpAgentTool],
        accumulated_chunks: Dict[str, Dict[str, Any]],
        terms: set,
        question_id: str
    ) -> Optional[str]:
        """Stage 3: the LLM gets only the chosen server's tools and must pick the one (and its arguments) that
        fulfils the request; the backend runs it. Returns a note for the research conversation, if any."""
        start_t = time.time()
        with span("mcp_choose_tool", stage="tool", server=server["name"]):
            calls = choose_tool_call(
                system=(
                    f"You fulfil the user's request with the tools of the MCP server '{server['name']}'. Pick the tool "
                    "that does what the request asks and fill in its arguments from the request. The relevant document "
                    "passages are supplied to the tool automatically."
                ),
                user=f"User request: {state.question}",
                tools=[t.declaration for t in mcp_tools.values()],
            )
        notes = []
        for call in calls:
            tool = mcp_tools.get(call.name)
            if not tool:
                continue
            with span(f"mcp_call:{tool.tool_name}", stage="tool", server=server["name"], args=dict(call.args)):
                summary = self._run_mcp_tool(state, tool, dict(call.args), accumulated_chunks, terms)
            latency_ms = (time.time() - start_t) * 1000
            state.record_step(
                action=f"mcp_call:{tool.tool_name}",
                input_summary=json.dumps(call.args),
                result_summary=json.dumps(summary)[:200],
                latency_ms=latency_ms,
                raw_args=dict(call.args),
                details={"server": server["name"]}
            )
            self.logger.log_step(
                question_id=question_id,
                step=state.iteration_count,
                action=f"mcp_call:{tool.tool_name}",
                safe_input_summary=f"args={call.args}",
                result_summary="ok" if "error" not in summary else "error",
                latency_ms=latency_ms,
                tokens=0,
                cost=0.0
            )
            notes.append(f"{tool.tool_name}: {json.dumps(summary)}")
        if not notes:
            return None
        return ("The MCP server already produced output for the user (shown as a card under your answer): "
                + "; ".join(notes) + ". In your final answer, refer to it in one short sentence; do not reproduce it.")

    def _ensure_evidence(self, state: AgentState, accumulated_chunks: Dict[str, Dict[str, Any]]) -> None:
        """Search the documents once if nothing was retrieved yet (budget ran out, or a tool needs context first)."""
        if accumulated_chunks:
            return
        res = search_document(query=state.question, document_id=state.document_id)
        for chunk in res.get("results", []):
            accumulated_chunks[f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"] = chunk
        state.retrieved_evidence = list(accumulated_chunks.values())

    def _run_mcp_tool(
        self,
        state: AgentState,
        tool: McpAgentTool,
        args: Dict[str, Any],
        accumulated_chunks: Dict[str, Dict[str, Any]],
        terms: set
    ) -> Dict[str, Any]:
        """Call an external MCP tool with the retrieved passages as context; keep its full result for the response."""
        self._ensure_evidence(state, accumulated_chunks)
        context = {"sources": prepare_sources(list(accumulated_chunks.values()), terms), "answer": ""}
        response = run_agent_tool(tool, args, context)
        state.mcp_results.append({
            "server_id": tool.server_id,
            "server_name": tool.server_name,
            "tool_name": tool.tool_name,
            "arguments": args,
            "success": bool(response.get("success")),
            "result": response.get("result"),
            "error": response.get("error"),
        })
        return summarize_for_llm(response)

    def _generate_final_answer(
        self,
        state: AgentState,
        accumulated_chunks: Dict[str, Dict[str, Any]]
    ):
        start_t = time.time()

        # A budget can run out before any search ran (e.g. while the LLM was rate-limited);
        # never answer without looking at the documents at least once
        self._ensure_evidence(state, accumulated_chunks)

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

        # Artifacts already built by MCP tools are shown as cards; the answer should point to them, not repeat them
        artifacts = [r["result"] for r in state.mcp_results if r.get("success") and is_artifact(r.get("result"))]
        extra = "".join(
            f"A {a.get('type')} titled '{a.get('title')}' is shown to the user under your answer. "
            "Refer to it in one short sentence and do not reproduce it as a table or list.\n"
            for a in artifacts
        )
        chat_res = llm_service.generate_answer(
            question=state.question,
            sources=citations,
            extra_instructions=extra
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

