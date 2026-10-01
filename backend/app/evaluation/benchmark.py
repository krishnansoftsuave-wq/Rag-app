import os
import json
import csv
import time
from typing import Dict, Any, List, Optional
from app.agents.rag_agent import AdaptiveRAGAgent
from app.workflows.fixed_rag_workflow import FixedRAGWorkflow
from app.evaluation.evaluator import evaluate_answer
from app.evaluation.metrics import summarize_metrics
from app.core.config import BASE_DIR

QUESTIONS_PATH = str(BASE_DIR / "benchmarks" / "questions.json")
RESULTS_DIR = str(BASE_DIR / "results")
RACE_CSV_PATH = str(BASE_DIR / "results" / "race.csv")
SUMMARY_JSON_PATH = str(BASE_DIR / "results" / "summary.json")


class BenchmarkRunner:
    def __init__(self, questions_file: Optional[str] = None):
        self.questions_file = questions_file or QUESTIONS_PATH
        self.agent = AdaptiveRAGAgent()
        self.workflow = FixedRAGWorkflow()

    def load_questions(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.questions_file):
            raise FileNotFoundError(f"Questions file not found at: {self.questions_file}")
        with open(self.questions_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _evaluate_trajectory_for_question(
        self,
        q_obj: Dict[str, Any],
        trace: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Evaluates tool-choice accuracy, argument validity, step efficiency, and trajectory pass."""
        expected_trajectory = q_obj.get("expected_trajectory", ["search_document", "validate_evidence", "generate_answer"])
        alternate_trajectories = q_obj.get("alternate_valid_trajectories", [expected_trajectory])
        expected_steps = q_obj.get("expected_steps", 2)

        actual_actions = [step.get("action") for step in trace]
        actual_tool_steps = [a for a in actual_actions if a != "generate_answer"]

        total_tool_decisions = len(actual_tool_steps)
        correct_tool_decisions = 0
        total_tool_arguments = len(trace)
        valid_tool_arguments = 0
        failure_modes = []

        # Check tool choice accuracy per step over tool calls
        for idx, act in enumerate(actual_tool_steps):
            is_valid_choice = False
            for alt in alternate_trajectories:
                alt_tool_steps = [a for a in alt if a != "generate_answer"]
                if idx < len(alt_tool_steps) and act == alt_tool_steps[idx]:
                    is_valid_choice = True
                    break
            if is_valid_choice:
                correct_tool_decisions += 1
            else:
                failure_modes.append("Wrong tool choice")

        # Validate arguments for each step in trace
        for step in trace:
            action = step.get("action")
            raw_args = step.get("raw_args", {})
            is_valid_arg = True
            arg_reason = ""

            if action in ["search_document", "refine_document_search"]:
                q_str = raw_args.get("query", "")
                if not q_str or not isinstance(q_str, str) or len(q_str.strip()) < 3:
                    is_valid_arg = False
                    arg_reason = "Search query is empty or too short (<3 chars)"
            elif action == "validate_evidence":
                q_str = raw_args.get("question", "")
                if not q_str or not isinstance(q_str, str):
                    is_valid_arg = False
                    arg_reason = "Question parameter missing or invalid"
            elif action == "generate_answer":
                q_str = raw_args.get("question", "")
                if not q_str or not isinstance(q_str, str):
                    is_valid_arg = False
                    arg_reason = "Question parameter missing"

            if is_valid_arg:
                valid_tool_arguments += 1
            else:
                failure_modes.append("Invalid arguments")

        # Check step efficiency & excessive steps
        steps_taken = len(actual_tool_steps)
        step_efficiency = round(steps_taken / max(1, expected_steps), 2)
        if steps_taken > expected_steps + 1:
            failure_modes.append("Excessive steps")

        # Check poor re-planning
        if "refine_document_search" in actual_actions and actual_actions.count("refine_document_search") > 2:
            failure_modes.append("Poor re-planning")

        # Trajectory pass status: exact match with expected or alternate trajectories & all arguments valid
        trajectory_passed = False
        for alt in alternate_trajectories:
            if actual_actions == alt:
                trajectory_passed = True
                break

        if failure_modes:
            trajectory_passed = False

        return {
            "trajectory_passed": trajectory_passed,
            "actual_trajectory": actual_actions,
            "expected_trajectory": expected_trajectory,
            "total_tool_decisions": total_tool_decisions,
            "correct_tool_decisions": correct_tool_decisions,
            "total_tool_arguments": total_tool_arguments,
            "valid_tool_arguments": valid_tool_arguments,
            "steps_taken": steps_taken,
            "expected_steps": expected_steps,
            "step_efficiency": step_efficiency,
            "detected_failure_modes": list(set(failure_modes)),
            "trajectory_failure_reason": ", ".join(set(failure_modes)) if failure_modes else ("Trajectory mismatch" if not trajectory_passed else "None")
        }

    def run_benchmark(
        self,
        system_type: str = "both",
        document_id: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        questions = self.load_questions()
        os.makedirs(RESULTS_DIR, exist_ok=True)

        agent_results = []
        workflow_results = []
        race_rows = []

        print(f"Executing benchmark on {len(questions)} questions (system mode: {system_type})...")

        for q in questions:
            qid = q["id"]
            q_text = q["question"]
            q_type = q.get("question_type", "factual")
            expected = q.get("expected_answer", "")
            doc_id = document_id or q.get("document_id")

            # Run Agent
            if system_type in ["agent", "both"]:
                print(f"  [Agent] Running {qid}...")
                agent_state = self.agent.run(
                    question=q_text,
                    document_id=doc_id,
                    question_id=qid,
                    api_key=api_key
                )
                eval_res = evaluate_answer(agent_state.final_answer, expected, q_type)
                trace_dicts = [t.to_dict() for t in agent_state.trace]
                traj_eval = self._evaluate_trajectory_for_question(q, trace_dicts)

                agent_entry = {
                    "system": "agent",
                    "question_id": qid,
                    "question": q_text,
                    "question_type": q_type,
                    "passed": eval_res["passed"],
                    "score": eval_res["score"],
                    "latency_ms": round(agent_state.elapsed_seconds * 1000, 2),
                    "input_tokens": agent_state.input_tokens,
                    "output_tokens": agent_state.output_tokens,
                    "total_tokens": agent_state.total_tokens,
                    "cost": round(agent_state.estimated_cost, 6),
                    "iterations": agent_state.iteration_count,
                    "termination_reason": agent_state.termination_reason,
                    "final_answer": agent_state.final_answer,
                    "trace": trace_dicts,
                    **traj_eval
                }
                agent_results.append(agent_entry)
                race_rows.append(agent_entry)

            # Run Workflow
            if system_type in ["workflow", "both"]:
                print(f"  [Workflow] Running {qid}...")
                workflow_state = self.workflow.run(
                    question=q_text,
                    document_id=doc_id,
                    question_id=qid,
                    api_key=api_key
                )
                eval_res = evaluate_answer(workflow_state.final_answer, expected, q_type)
                trace_dicts = [t.to_dict() for t in workflow_state.trace]
                traj_eval = self._evaluate_trajectory_for_question(q, trace_dicts)

                workflow_entry = {
                    "system": "workflow",
                    "question_id": qid,
                    "question": q_text,
                    "question_type": q_type,
                    "passed": eval_res["passed"],
                    "score": eval_res["score"],
                    "latency_ms": round(workflow_state.elapsed_seconds * 1000, 2),
                    "input_tokens": workflow_state.input_tokens,
                    "output_tokens": workflow_state.output_tokens,
                    "total_tokens": workflow_state.total_tokens,
                    "cost": round(workflow_state.estimated_cost, 6),
                    "iterations": workflow_state.iteration_count,
                    "termination_reason": workflow_state.termination_reason,
                    "final_answer": workflow_state.final_answer,
                    "trace": trace_dicts,
                    **traj_eval
                }
                workflow_results.append(workflow_entry)
                race_rows.append(workflow_entry)

        # Write race.csv
        fieldnames = [
            "system", "question_id", "question_type", "passed", "trajectory_passed",
            "latency_ms", "input_tokens", "output_tokens", "total_tokens",
            "cost", "iterations", "step_efficiency", "termination_reason"
        ]
        with open(RACE_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in race_rows:
                writer.writerow({k: row[k] for k in fieldnames})

        # Calculate Summaries & Verdict
        agent_summary = summarize_metrics(agent_results)
        workflow_summary = summarize_metrics(workflow_results)

        verdict_text = self._generate_verdict(agent_summary, workflow_summary, agent_results, workflow_results)

        # Calculate mitigation price (Fixed Workflow vs Original Agent)
        mitigation_price = {
            "mitigation_description": "Replacing dynamic agent with deterministic Fixed RAG Workflow",
            "latency_delta_ms": round(workflow_summary.get("p50_latency_ms", 0) - agent_summary.get("p50_latency_ms", 0), 2),
            "token_delta_per_question": round((workflow_summary.get("total_tokens", 0) - agent_summary.get("total_tokens", 0)) / max(1, len(questions)), 1),
            "cost_delta_per_question": round(workflow_summary.get("cost_per_question", 0) - agent_summary.get("cost_per_question", 0), 6),
            "outcome_pass_rate_delta": round(workflow_summary.get("outcome_pass_rate", 0) - agent_summary.get("outcome_pass_rate", 0), 2),
            "trajectory_pass_rate_delta": round(workflow_summary.get("trajectory_pass_rate", 0) - agent_summary.get("trajectory_pass_rate", 0), 2)
        }

        # Build Regression Matrix table (Failure Mode comparison)
        regression_matrix = []
        all_modes = ["Wrong tool choice", "Invalid arguments", "Excessive steps", "Poor re-planning", "Other trajectory failures"]
        ag_failures = agent_summary.get("failure_modes", {})
        wf_failures = workflow_summary.get("failure_modes", {})

        for mode in all_modes:
            orig = ag_failures.get(mode, 0)
            fixed = wf_failures.get(mode, 0)
            change = fixed - orig
            regression_matrix.append({
                "failure_mode": mode,
                "original_agent": orig,
                "fixed_agent": fixed,
                "change": f"+{change}" if change > 0 else str(change)
            })

        # Comparison table format for Week 8 metrics
        comparison_table = {
            "tool_choice_accuracy": {"original_agent": f"{agent_summary['tool_choice_accuracy']}%", "fixed_agent": f"{workflow_summary['tool_choice_accuracy']}%"},
            "argument_validity_rate": {"original_agent": f"{agent_summary['argument_validity_rate']}%", "fixed_agent": f"{workflow_summary['argument_validity_rate']}%"},
            "step_efficiency": {"original_agent": agent_summary['step_efficiency'], "fixed_agent": workflow_summary['step_efficiency']},
            "cost_p50": {"original_agent": f"${agent_summary['cost_p50']}", "fixed_agent": f"${workflow_summary['cost_p50']}"},
            "cost_max": {"original_agent": f"${agent_summary['cost_max']}", "fixed_agent": f"${workflow_summary['cost_max']}"},
            "outcome_pass_rate": {"original_agent": f"{agent_summary['outcome_pass_rate']}%", "fixed_agent": f"{workflow_summary['outcome_pass_rate']}%"},
            "trajectory_pass_rate": {"original_agent": f"{agent_summary['trajectory_pass_rate']}%", "fixed_agent": f"{workflow_summary['trajectory_pass_rate']}%"},
            "outcome_vs_trajectory_gap": {"original_agent": f"{agent_summary['outcome_vs_trajectory_gap']}%", "fixed_agent": f"{workflow_summary['outcome_vs_trajectory_gap']}%"}
        }

        summary_data = {
            "agent": agent_summary,
            "workflow": workflow_summary,
            "verdict": verdict_text,
            "comparison_table": comparison_table,
            "mitigation_price": mitigation_price,
            "regression_matrix": regression_matrix,
            "agent_question_results": agent_results,
            "workflow_question_results": workflow_results
        }

        with open(SUMMARY_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2)

        print(f"Benchmark run complete! Results written to {RACE_CSV_PATH} and {SUMMARY_JSON_PATH}.")
        return summary_data

    def _generate_verdict(
        self,
        agent_meta: Dict[str, Any],
        wf_meta: Dict[str, Any],
        agent_q: List[Dict[str, Any]],
        wf_q: List[Dict[str, Any]]
    ) -> str:
        """Generates dynamic final verdict based on trajectory & outcome metrics."""
        wf_pass = wf_meta.get("pass_rate", 0)
        ag_pass = agent_meta.get("pass_rate", 0)
        wf_lat = wf_meta.get("p50_latency_ms", 0)
        ag_lat = agent_meta.get("p50_latency_ms", 0)
        wf_cost = wf_meta.get("cost_per_question", 0)
        ag_cost = agent_meta.get("cost_per_question", 0)

        ag_gap = agent_meta.get("outcome_vs_trajectory_gap", 0)
        wf_gap = wf_meta.get("outcome_vs_trajectory_gap", 0)

        verdict = (
            f"Original Agent achieved {ag_pass}% outcome pass rate (trajectory pass: {agent_meta.get('trajectory_pass_rate', 0)}%, gap: {ag_gap}%) "
            f"with P50 latency of {ag_lat:.0f}ms and cost P50 of ${agent_meta.get('cost_p50', 0)}. "
            f"Fixed Agent (Workflow) achieved {wf_pass}% outcome pass rate (trajectory pass: {wf_meta.get('trajectory_pass_rate', 0)}%, gap: {wf_gap}%) "
            f"with P50 latency of {wf_lat:.0f}ms and cost P50 of ${wf_meta.get('cost_p50', 0)}."
        )
        return verdict
