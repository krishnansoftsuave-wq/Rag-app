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


STRING_CHECKS = ("must_contain", "must_not_contain", "must_not_contain_in_code")


def code_blocks(text: str) -> str:
    """The code in the answer's fenced code blocks (```...```), i.e. what a user would copy and run, without comments:
    a comment such as "# NovaClient.connect() was removed, use Client()" warns about a method, it does not call it."""
    code = "\n".join(re.findall(r"```[^\n]*\n(.*?)```", text or "", flags=re.DOTALL))
    return re.sub(r"(^|\s)(#|//).*$", "", code, flags=re.MULTILINE)


def evaluate_case(generated_answer: str, case: Dict[str, Any]) -> Dict[str, Any]:
    """A case with string checks (e.g. code identifiers) is judged on those exactly, case-insensitively:
    must_contain anywhere, must_not_contain anywhere, must_not_contain_in_code inside fenced code blocks only (naming
    a deprecated method in prose is fine, calling it in a code sample is not). Any other case falls back to keyword
    overlap with its expected answer."""
    if not any(k in case for k in STRING_CHECKS):
        return evaluate_answer(generated_answer, case["expected"], case["category"])
    text = (generated_answer or "").lower()
    code = code_blocks(generated_answer).lower()
    missing = [s for s in case.get("must_contain", []) if s.lower() not in text]
    forbidden = [s for s in case.get("must_not_contain", []) if s.lower() in text]
    forbidden_code = [s for s in case.get("must_not_contain_in_code", []) if s.lower() in code]
    problems = ([f"missing {missing}"] if missing else []) + ([f"contains forbidden {forbidden}"] if forbidden else []) \
        + ([f"code sample uses {forbidden_code}"] if forbidden_code else [])
    return {
        "passed": not problems,
        "score": 0.0 if problems else 1.0,
        "reason": "; ".join(problems) or "All required strings present, no forbidden ones.",
    }
