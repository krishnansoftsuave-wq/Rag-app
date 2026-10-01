import numpy as np
from typing import List, Dict, Any


def calculate_p50_latency(latencies_ms: List[float]) -> float:
    """Calculates median (P50) latency in milliseconds."""
    if not latencies_ms:
        return 0.0
    return float(np.median(latencies_ms))


def calculate_p50_cost(costs: List[float]) -> float:
    """Calculates median (P50) cost in USD."""
    if not costs:
        return 0.0
    return round(float(np.median(costs)), 6)


def calculate_max_cost(costs: List[float]) -> float:
    """Calculates max (P100) cost in USD."""
    if not costs:
        return 0.0
    return round(float(np.max(costs)), 6)


def calculate_pass_rate(passed_flags: List[bool]) -> float:
    """Calculates pass rate percentage (0.0 to 100.0)."""
    if not passed_flags:
        return 0.0
    return round((sum(passed_flags) / len(passed_flags)) * 100.0, 2)


def summarize_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarizes comprehensive Week 8 benchmark & trajectory metrics for a system.
    """
    if not results:
        return {
            "pass_rate": 0.0,
            "outcome_pass_rate": 0.0,
            "trajectory_pass_rate": 0.0,
            "outcome_vs_trajectory_gap": 0.0,
            "tool_choice_accuracy": 0.0,
            "argument_validity_rate": 0.0,
            "step_efficiency": 0.0,
            "p50_latency_ms": 0.0,
            "cost_p50": 0.0,
            "cost_max": 0.0,
            "total_tokens": 0,
            "cost_per_question": 0.0,
            "total_cost": 0.0,
            "total_questions": 0,
            "failure_modes": {},
            "gap_cases": []
        }

    passed_flags = [r.get("passed", False) for r in results]
    traj_passed_flags = [r.get("trajectory_passed", False) for r in results]
    latencies = [r.get("latency_ms", 0.0) for r in results]
    costs = [r.get("cost", 0.0) for r in results]
    total_tokens = sum([r.get("total_tokens", 0) for r in results])
    total_cost = sum(costs)
    count = len(results)

    # Tool decision & argument validity accumulators
    total_tool_decisions = sum([r.get("total_tool_decisions", 0) for r in results])
    correct_tool_decisions = sum([r.get("correct_tool_decisions", 0) for r in results])

    total_tool_args = sum([r.get("total_tool_arguments", 0) for r in results])
    valid_tool_args = sum([r.get("valid_tool_arguments", 0) for r in results])

    # Step efficiency calculation: avg(steps_taken / expected_steps)
    efficiencies = [r.get("step_efficiency", 1.0) for r in results]
    avg_step_efficiency = round(float(np.mean(efficiencies)), 2) if efficiencies else 1.0

    tool_choice_acc = round((correct_tool_decisions / total_tool_decisions) * 100.0, 2) if total_tool_decisions > 0 else 100.0
    arg_validity_rate = round((valid_tool_args / total_tool_args) * 100.0, 2) if total_tool_args > 0 else 100.0

    outcome_pass_rate = calculate_pass_rate(passed_flags)
    trajectory_pass_rate = calculate_pass_rate(traj_passed_flags)
    gap = round(outcome_pass_rate - trajectory_pass_rate, 2)

    # Identify gap cases (Outcome PASS + Trajectory FAIL)
    gap_cases = []
    for r in results:
        if r.get("passed") and not r.get("trajectory_passed"):
            gap_cases.append({
                "question_id": r.get("question_id"),
                "question": r.get("question"),
                "actual_trajectory": r.get("actual_trajectory", []),
                "expected_trajectory": r.get("expected_trajectory", []),
                "reason": r.get("trajectory_failure_reason", "Trajectory mismatch")
            })

    # Count failure modes across all test cases
    failure_counts = {
        "Wrong tool choice": 0,
        "Invalid arguments": 0,
        "Excessive steps": 0,
        "Poor re-planning": 0,
        "Other trajectory failures": 0
    }

    for r in results:
        for mode in r.get("detected_failure_modes", []):
            if mode in failure_counts:
                failure_counts[mode] += 1
            else:
                failure_counts["Other trajectory failures"] += 1

    return {
        "pass_rate": outcome_pass_rate,
        "outcome_pass_rate": outcome_pass_rate,
        "trajectory_pass_rate": trajectory_pass_rate,
        "outcome_vs_trajectory_gap": gap,
        "tool_choice_accuracy": tool_choice_acc,
        "argument_validity_rate": arg_validity_rate,
        "step_efficiency": avg_step_efficiency,
        "p50_latency_ms": round(calculate_p50_latency(latencies), 2),
        "cost_p50": calculate_p50_cost(costs),
        "cost_max": calculate_max_cost(costs),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 6),
        "cost_per_question": round(total_cost / count, 6) if count > 0 else 0.0,
        "total_questions": count,
        "failure_modes": failure_counts,
        "gap_cases": gap_cases
    }
