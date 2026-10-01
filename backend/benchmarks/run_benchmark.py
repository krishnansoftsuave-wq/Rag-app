import sys
import os
import argparse

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.evaluation.benchmark import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="DocuBrain Week 7 Benchmark Runner")
    parser.add_argument(
        "--system",
        choices=["agent", "workflow", "both"],
        default="both",
        help="System to execute benchmark against: 'agent', 'workflow', or 'both'"
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Optional document ID to evaluate against"
    )

    args = parser.parse_args()

    print(f"Starting DocuBrain Benchmark (System: {args.system})...")
    runner = BenchmarkRunner()
    results = runner.run_benchmark(system_type=args.system, document_id=args.doc_id)
    print("\nBenchmark Summary:")
    print("--------------------------------------------------")
    if "agent" in results and results["agent"].get("total_questions", 0) > 0:
        ag = results["agent"]
        print(f"AGENT:    Pass Rate: {ag['pass_rate']}% | P50 Latency: {ag['p50_latency_ms']}ms | Total Tokens: {ag['total_tokens']} | Cost/Q: ${ag['cost_per_question']:.4f}")
    if "workflow" in results and results["workflow"].get("total_questions", 0) > 0:
        wf = results["workflow"]
        print(f"WORKFLOW: Pass Rate: {wf['pass_rate']}% | P50 Latency: {wf['p50_latency_ms']}ms | Total Tokens: {wf['total_tokens']} | Cost/Q: ${wf['cost_per_question']:.4f}")
    print("--------------------------------------------------")
    print(f"Verdict: {results.get('verdict', '')}\n")


if __name__ == "__main__":
    main()
