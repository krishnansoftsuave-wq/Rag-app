import logging
import os
from typing import Optional
from app.core.logger import get_logger

logger = get_logger("agent_execution")


class AgentExecutionLogger:
    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path
        if log_file_path:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
            self.file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            self.file_handler.setFormatter(formatter)
            logger.addHandler(self.file_handler)
        else:
            self.file_handler = None

    def log_step(
        self,
        question_id: str,
        step: int,
        action: str,
        safe_input_summary: str,
        result_summary: str,
        latency_ms: float,
        tokens: int = 0,
        cost: float = 0.0,
        budget_status: Optional[str] = None
    ):
        log_line = (
            f"[Agent] question_id={question_id} step={step} action={action} "
            f"input_summary=\"{safe_input_summary}\" result_summary=\"{result_summary}\" "
            f"latency_ms={round(latency_ms, 1)} tokens={tokens} cost=${cost:.5f}"
        )
        if budget_status:
            log_line += f" budget={budget_status}"
        logger.info(log_line)

    def log_termination(self, question_id: str, reason: str, total_steps: int, total_cost: float, total_tokens: int):
        log_line = (
            f"[Agent] question_id={question_id} termination={reason} "
            f"total_steps={total_steps} total_tokens={total_tokens} total_cost=${total_cost:.5f}"
        )
        logger.info(log_line)

    def close(self):
        if self.file_handler:
            logger.removeHandler(self.file_handler)
            self.file_handler.close()
