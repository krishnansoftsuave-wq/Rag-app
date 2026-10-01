import os
import time
from dataclasses import dataclass
from typing import Tuple, Optional
from app.agents.state import AgentState


@dataclass
class AgentBudgets:
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "8"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "8000"))
    max_cost: float = float(os.getenv("MAX_COST", "0.05"))
    max_wall_clock_seconds: float = float(os.getenv("MAX_WALL_CLOCK_SECONDS", "15.0"))

    def check_budgets(self, state: AgentState) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether any of the four safety budgets have been exceeded.
        Returns (is_exceeded, termination_reason).
        """
        # 1. Iterations Budget
        if state.iteration_count >= self.max_iterations:
            return True, "max_iterations"

        # 2. Tokens Budget
        if state.total_tokens >= self.max_tokens:
            return True, "max_tokens"

        # 3. Cost Budget
        if state.estimated_cost >= self.max_cost:
            return True, "max_cost"

        # 4. Wall Clock Budget
        elapsed = time.time() - state.start_time
        if elapsed >= self.max_wall_clock_seconds:
            return True, "wall_clock"

        return False, None

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_tokens": self.max_tokens,
            "max_cost": self.max_cost,
            "max_wall_clock_seconds": self.max_wall_clock_seconds
        }
