"""Reduce long retrieved chunks to the sentences relevant to a question, within a character budget.

Agentic chunking can produce chunks of 10K+ characters. Sending them whole to the LLM wastes tokens and
can exceed per-request limits (e.g. Groq free tier rejects requests above its tokens-per-minute cap), while
cutting them at a fixed length drops facts that sit deep inside the chunk.
"""
import re
from typing import Any, Dict, List, Set

_STOPWORDS = {"the", "and", "for", "are", "was", "with", "that", "this", "from", "per", "each", "what", "how", "which", "does"}


def focus_terms(*texts: str) -> Set[str]:
    """Lower-cased words (3+ chars) and numbers from the question/answer used to score sentences."""
    words = re.findall(r"[\w$%.]+", " ".join(texts).lower())
    return {w.strip(".") for w in words if len(w.strip(".")) >= 3 and w.strip(".") not in _STOPWORDS}


def focused_excerpt(content: str, terms: Set[str], limit: int) -> str:
    """Keep a long chunk's sentences that best match the terms, in document order, within limit."""
    if len(content) <= limit:
        return content
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", content) if s.strip()]
    scored = []
    for idx, sentence in enumerate(sentences):
        words = set(re.findall(r"[\w$%.]+", sentence.lower()))
        # Numbers (prices, dates, percentages) are the strongest signal of a relevant sentence
        score = sum(3 if any(ch.isdigit() for ch in w) else 1 for w in words & terms)
        scored.append((score, idx, sentence))
    picked, used = [], 0
    for score, idx, sentence in sorted(scored, key=lambda t: (-t[0], t[1])):
        if used + len(sentence) + 1 > limit:
            continue
        picked.append((idx, sentence))
        used += len(sentence) + 1
    return " ".join(sentence for _, sentence in sorted(picked))


def prepare_sources(
    chunks: List[Dict[str, Any]],
    terms: Set[str],
    max_sources: int = 8,
    per_source_chars: int = 2000,
    total_chars: int = 10000,
) -> List[Dict[str, Any]]:
    """Retrieved chunks as [{filename, chunk_index, content}] excerpts, for tools that take document context."""
    prepared, used = [], 0
    for chunk in chunks[:max_sources]:
        if used >= total_chars:
            break
        content = str(chunk.get("full_content") or chunk.get("content") or "")
        excerpt = focused_excerpt(content, terms, min(per_source_chars, total_chars - used))
        used += len(excerpt)
        prepared.append({"filename": chunk.get("filename", "Unknown"), "chunk_index": chunk.get("chunk_index", 0), "content": excerpt})
    return prepared
