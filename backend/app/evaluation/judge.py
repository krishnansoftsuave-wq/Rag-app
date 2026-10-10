"""
Blind LLM judge for the single-vs-team race. It sees the question, the reference answer, the parts the question
asks for, the documentation pages the reference was written from and one answer, never which system wrote it. It runs on a different model family from the contestants
(and outside their usage meters), so its tokens are not charged to either side and it does not grade its own
model's writing.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from app.services.llm.client import complete

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen/qwen3.8-27b")
JUDGE_VERSION = 2  # bump when the rubric changes; runs scored by an older version are judged again
PASS_MIN_SCORE = 4  # a run passes when every dimension scores at least this
DIMENSIONS = ("correctness", "completeness", "groundedness")


def judge_answer(question: str, reference: str, answer: str, asks: Optional[List[str]] = None,
                 evidence: str = "", model: Optional[str] = None) -> Dict[str, Any]:
    """Scores 1-5 for correctness, completeness and groundedness, their mean as quality, and pass/fail.
    evidence is the documentation the reference was written from; groundedness is checked against it.
    Raises LLMUnavailableError when the judge model cannot answer, ValueError when its reply is unreadable."""
    if not (answer or "").strip():
        return {**{d: 1 for d in DIMENSIONS}, "quality": 1.0, "passed": False, "missing": asks or [],
                "errors": ["empty answer"], "rationale": "Empty answer."}
    parts = "\n".join(f"- {a}" for a in asks) if asks else "- (as stated in the question)"
    source = f"\nDocumentation (the source of truth):\n\"\"\"{evidence}\"\"\"\n" if evidence else ""
    prompt = f"""You grade answers from a documentation assistant against a reference answer written from the documentation.
{source}
Question: {question}

Parts the question asks for:
{parts}

Reference answer: {reference}

Answer to grade:
\"\"\"{answer}\"\"\"

Score each dimension from 1 (bad) to 5 (perfect):
- correctness: the facts, values and conclusions in the answer agree with the reference. A wrong number, name or yes/no is a serious error.
- completeness: the answer covers every part listed above.
- groundedness: every specific claim in the answer (value, limit, feature, behaviour, example use case) is supported by the documentation or the reference. 5 = nothing unsupported; 4 = one minor unsupported detail; 3 = several unsupported details; 1-2 = invented values or facts, or a value supplied for something the reference says the documentation does not cover. List each unsupported claim under errors.
Judge content only: do not reward length, formatting or confidence. Extra details that the documentation supports neither add nor subtract.

Reply with JSON only:
{{"correctness": <1-5>, "completeness": <1-5>, "groundedness": <1-5>, "missing": ["<part not answered>"], "errors": ["<wrong or invented claim>"], "rationale": "<one sentence>"}}"""
    text, _ = complete(prompt, json_mode=True, models=[model or JUDGE_MODEL], temperature=0)
    data = _parse(text)
    try:
        scores = {d: min(5, max(1, int(data[d]))) for d in DIMENSIONS}
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Unreadable judge reply: {text[:200]!r}")
    return {
        **scores,
        "quality": round(sum(scores.values()) / len(scores), 3),
        "passed": all(s >= PASS_MIN_SCORE for s in scores.values()),
        "missing": [str(m) for m in data.get("missing", []) or []],
        "errors": [str(e) for e in data.get("errors", []) or []],
        "rationale": str(data.get("rationale", "")),
    }


def _parse(text: str) -> Dict[str, Any]:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return {}
