import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.budgets import AgentBudgets
from app.agents.logger import AgentExecutionLogger
from app.agents.rag_agent import AdaptiveRAGAgent
from app.core.config import BASE_DIR

LOG_PATH = str(BASE_DIR / "logs" / "budget_termination.log")


def run_budget_termination_test():
    print("Testing intentional safety budget termination...")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    # Initialize logger with specific log file
    agent_logger = AgentExecutionLogger(log_file_path=LOG_PATH)

    # Strictly set MAX_ITERATIONS = 2 to trigger budget termination
    restricted_budgets = AgentBudgets(
        max_iterations=2,
        max_tokens=8000,
        max_cost=0.05,
        max_wall_clock_seconds=120.0
    )

    agent = AdaptiveRAGAgent(budgets=restricted_budgets, logger=agent_logger)

    # Run a question that requires multiple iterations
    question = "What happens if authentication fails during deployment and how does query refinement work?"
    print(f"Running Agent with MAX_ITERATIONS=2 on question: '{question}'...")

    state = agent.run(question=question, question_id="test_budget_max_iter")

    print(f"Agent state completed: {state.completed}")
    print(f"Termination reason: '{state.termination_reason}'")
    print(f"Total iterations: {state.iteration_count}")

    agent_logger.close()

    assert state.termination_reason == "max_iterations", f"Expected 'max_iterations' but got '{state.termination_reason}'"
    assert os.path.exists(LOG_PATH), f"Log file was not created at {LOG_PATH}"

    print(f"SUCCESS: Budget termination test passed! Log saved to {LOG_PATH}")


if __name__ == "__main__":
    run_budget_termination_test()
