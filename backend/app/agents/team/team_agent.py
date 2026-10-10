"""
Docs squad: a manager plus two specialists (concepts, reference), raced against the single AdaptiveRAGAgent.

    question -> manager.plan -> [concepts | reference] in parallel, via A2A tasks -> manager.synthesize -> answer

Same interface as AdaptiveRAGAgent.run (returns an AgentState), same retriever, tools and LLM. Token counts are
the provider-reported usage, recorded per role (manager.plan, concepts, reference, manager.synthesize).
"""
import contextvars
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from app.services.retrieval.version_policy import question_scope
from app.agents.budgets import AgentBudgets
from app.agents.logger import AgentExecutionLogger
from app.agents.state import AgentState
from app.agents.team.a2a import Message, Task, TaskState, send_message
from app.agents.team.manager import HANDOFF_MODES, Manager
from app.agents.team.specialists import Specialist, build_specialists
from app.agents.tools import estimate_tokens
from app.core.tracing import span
from app.services.llm.client import LLMUnavailableError, UsageMeter, track_usage, usage_label


class TeamRAGAgent:
    def __init__(
        self,
        handoff: str = "findings",
        budgets: Optional[AgentBudgets] = None,
        logger: Optional[AgentExecutionLogger] = None,
        specialists: Optional[List[Specialist]] = None,
        manager: Optional[Manager] = None,
    ):
        if handoff not in HANDOFF_MODES:
            raise ValueError(f"handoff must be one of {HANDOFF_MODES}")
        self.handoff = handoff
        self.budgets = budgets or AgentBudgets()
        self.logger = logger or AgentExecutionLogger()
        self.specialists = specialists or build_specialists()
        self.manager = manager or Manager()

    @property
    def cards(self):
        return [s.card for s in self.specialists]

    def run(
        self,
        question: str,
        document_id: Optional[str] = None,
        question_id: str = "q_team",
        top_k: int = 4
    ) -> AgentState:
        # Archived docs are searched only if the question asks about an older version (retrieval/version_policy.py)
        with question_scope(question):
            return self._run(question, document_id, question_id, top_k)

    def _run(self, question: str, document_id: Optional[str], question_id: str, top_k: int) -> AgentState:
        state = AgentState(question=question, document_id=document_id)
        # Same wall-clock budget as the single agent; specialists stop searching and report when it runs out
        deadline = state.start_time + self.budgets.max_wall_clock_seconds

        with track_usage() as meter:
            # 1. Plan: which specialist gets which part of the question
            start = time.time()
            with usage_label("manager.plan"), span("manager.plan", stage="generation"):
                sub_tasks, fallback_plan = self.manager.plan(question, self.cards)
            self._record(
                state, meter, question_id, "manager.plan", "manager_plan",
                latency_ms=(time.time() - start) * 1000,
                input_summary=f"question_len={len(question)}",
                result_summary=f"sub_tasks={[st.to for st in sub_tasks]} fallback={fallback_plan}",
                details={"sub_tasks": [vars(st) for st in sub_tasks], "fallback_plan": fallback_plan},
            )

            # 2. Hand each sub-task to its specialist as an A2A task; they run in parallel
            by_name = {s.name: s for s in self.specialists}
            handoffs = [
                (by_name[st.to], Message.build("user", st.ask, {"document_id": document_id, "deadline": deadline}))
                for st in sub_tasks
            ]
            with ThreadPoolExecutor(max_workers=len(handoffs)) as pool:
                # Each thread gets a copy of this context, so its LLM calls land in the same usage meters
                futures = [pool.submit(contextvars.copy_context().run, self._delegate, spec, msg, question_id)
                           for spec, msg in handoffs]
                tasks: List[Task] = [f.result() for f in futures]
            outage = next((t for t in tasks if t.error_type == LLMUnavailableError.__name__), None)
            if outage:
                # The LLM itself was unavailable: an outage, not an answer (the single agent raises the same error)
                raise LLMUnavailableError(outage.status_message)

            evidence: Dict[str, Dict[str, Any]] = {}
            for (spec, msg), task in zip(handoffs, tasks):
                findings = task.artifact("findings")
                for chunk in task.artifact("evidence").get("chunks", []):
                    evidence[f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"] = chunk
                self._record(
                    state, meter, question_id, spec.name, f"a2a_task:{spec.name}",
                    latency_ms=task.duration_ms,
                    input_summary=msg.text[:200],
                    result_summary=f"state={task.state.value} findings={len(findings.get('findings', []))} "
                                   f"not_found={len(findings.get('not_found', []))} searches={findings.get('searches', 0)}",
                    details={"task": {k: v for k, v in task.to_dict().items() if k != "artifacts"},
                             "findings": findings, "card": spec.card.to_dict()},
                    raw_args={"query": msg.text},
                )
            state.retrieved_evidence = list(evidence.values())
            state.tool_results = [{"specialist": spec.name, "state": task.state.value, **task.artifact("findings")}
                                  for (spec, _), task in zip(handoffs, tasks)]

            # 3. Synthesize: the manager writes the answer from what the specialists handed back
            report = self.manager.handoff_report([(spec.name, msg.text, task) for (spec, msg), task in zip(handoffs, tasks)], self.handoff)
            start = time.time()
            with usage_label("manager.synthesize"), span("manager.synthesize", stage="generation"):
                answer = self.manager.synthesize(question, report)
            handoff_tokens = estimate_tokens(" ".join(msg.text for _, msg in handoffs)) + estimate_tokens(report)
            self._record(
                state, meter, question_id, "manager.synthesize", "manager_synthesize",
                latency_ms=(time.time() - start) * 1000,
                input_summary=f"handoff={self.handoff} report_chars={len(report)}",
                result_summary=f"answer_length={len(answer)}",
                details={"handoff_mode": self.handoff, "handoff_tokens_approx": handoff_tokens},
                raw_args={"question": question},
            )

        state.final_answer = answer
        state.completed = True
        state.termination_reason = "completed" if all(t.state == TaskState.COMPLETED for t in tasks) else "completed_partial"
        state.elapsed_seconds = time.time() - state.start_time
        self.logger.log_termination(question_id, state.termination_reason, state.iteration_count,
                                    state.estimated_cost, state.total_tokens)
        return state

    @staticmethod
    def _delegate(specialist: Specialist, message: Message, context_id: str) -> Task:
        # A specialist's searches are their own retrieval spans; its remaining LLM calls count as generation
        with usage_label(specialist.name), span(f"a2a_task:{specialist.name}", stage="generation"):
            return send_message(specialist, message, context_id=context_id)

    def _record(
        self,
        state: AgentState,
        meter: UsageMeter,
        question_id: str,
        label: str,
        action: str,
        latency_ms: float,
        input_summary: str,
        result_summary: str,
        details: Optional[Dict[str, Any]] = None,
        raw_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record one team step with the real tokens and cost of the LLM calls made under its label."""
        usage = meter.by_label().get(label, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
        state.record_step(
            action=action,
            input_summary=input_summary,
            result_summary=result_summary,
            latency_ms=latency_ms,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            step_cost=usage["cost"],
            details={**(details or {}), "llm_calls": usage["calls"]},
            raw_args=raw_args or {},
        )
        self.logger.log_step(
            question_id=question_id,
            step=state.iteration_count,
            action=action,
            safe_input_summary=input_summary[:120],
            result_summary=result_summary,
            latency_ms=latency_ms,
            tokens=usage["input_tokens"] + usage["output_tokens"],
            cost=usage["cost"],
        )
