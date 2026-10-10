"""
Per-model token prices, used to turn the usage a provider reports into dollars.

Prices are USD per 1M tokens from Groq's model pages (console.groq.com/docs/model/<model>), checked 2026-10-09.
A model missing here is reported as unpriced instead of being costed with another model's price.
"""
from typing import Dict, Optional

PRICES_PER_1M: Dict[str, Dict[str, float]] = {
    "openai/gpt-oss-120b": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.075, "cached_input": 0.037, "output": 0.30},
    "qwen/qwen3.8-27b": {"input": 0.80, "cached_input": 0.80, "output": 4.00},  # no cached rate listed
}


def call_cost(model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int) -> Optional[float]:
    """USD for one call; cached input tokens (part of input_tokens) are billed at the cached rate.
    None when the model has no known price."""
    price = PRICES_PER_1M.get(model)
    if price is None:
        return None
    uncached = max(0, input_tokens - cached_input_tokens)
    return (uncached * price["input"] + cached_input_tokens * price["cached_input"] + output_tokens * price["output"]) / 1_000_000
