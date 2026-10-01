import re
from typing import Dict, Any


def evaluate_answer(generated_answer: str, expected_answer: str, question_type: str) -> Dict[str, Any]:
    """
    Evaluates whether the generated answer contains key concept words and facts from expected_answer.
    Returns {"passed": bool, "score": float, "reason": str}.
    """
    if not generated_answer or not generated_answer.strip():
        return {
            "passed": False,
            "score": 0.0,
            "reason": "Empty generated answer."
        }

    gen_lower = generated_answer.lower()
    exp_lower = expected_answer.lower()

    # Extract key terms (length > 3)
    exp_words = set(re.findall(r'\b[a-z0-9_-]{4,}\b', exp_lower))
    stop_words = {"this", "that", "with", "from", "have", "were", "which", "their", "about", "uses", "used"}
    keywords = [w for w in exp_words if w not in stop_words]

    if not keywords:
        return {"passed": True, "score": 1.0, "reason": "No restrictive keywords found."}

    matched = [w for w in keywords if w in gen_lower]
    score = len(matched) / len(keywords)

    # Threshold for pass
    threshold = 0.35 if question_type in ["ambiguous", "multi_hop"] else 0.45
    passed = score >= threshold

    return {
        "passed": passed,
        "score": round(score, 2),
        "reason": f"Matched {len(matched)}/{len(keywords)} key concept terms ({int(score*100)}%)."
    }
