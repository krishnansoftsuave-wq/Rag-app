"""Chat artifacts: built by an external MCP server exposing `generate_artifact` (e.g. mcp_servers/artifact_studio)."""
import re
from typing import Any, Dict, List

from app.mcp.client.manager import mcp_client_manager

ARTIFACT_TOOL_NAME = "generate_artifact"
MAX_ARTIFACT_SOURCES = 8
MAX_ARTIFACT_SOURCE_CHARS = 2000
MAX_ARTIFACT_TOTAL_CHARS = 10000
_EXCERPT_STOPWORDS = {"the", "and", "for", "are", "was", "with", "that", "this", "from", "per", "each", "what", "how", "which", "does"}


def _focused_excerpt(content: str, focus_terms: set, limit: int) -> str:
    """Keep a long chunk's sentences that best match the question and answer, in document order, within limit."""
    if len(content) <= limit:
        return content
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", content) if s.strip()]
    scored = []
    for idx, sentence in enumerate(sentences):
        words = set(re.findall(r"[\w$%.]+", sentence.lower()))
        # Numbers from the answer (prices, dates, percentages) are the strongest signal of a relevant sentence
        score = sum(3 if any(ch.isdigit() for ch in w) else 1 for w in words & focus_terms)
        scored.append((score, idx, sentence))
    picked, used = [], 0
    for score, idx, sentence in sorted(scored, key=lambda t: (-t[0], t[1])):
        if used + len(sentence) + 1 > limit:
            continue
        picked.append((idx, sentence))
        used += len(sentence) + 1
    return " ".join(sentence for _, sentence in sorted(picked))


def _prepare_sources(question: str, answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reduce long chunks to their sentences matching the question/answer, not cut at a fixed length,
    so facts deep inside a chunk still reach the artifact model within the token budget."""
    focus_terms = {
        w.strip(".") for w in re.findall(r"[\w$%.]+", f"{question} {answer}".lower())
        if len(w.strip(".")) >= 3 and w.strip(".") not in _EXCERPT_STOPWORDS
    }
    prepared, total_chars = [], 0
    for s in sources[:MAX_ARTIFACT_SOURCES]:
        if total_chars >= MAX_ARTIFACT_TOTAL_CHARS:
            break
        limit = min(MAX_ARTIFACT_SOURCE_CHARS, MAX_ARTIFACT_TOTAL_CHARS - total_chars)
        excerpt = _focused_excerpt(str(s.get("content", "")), focus_terms, limit)
        total_chars += len(excerpt)
        prepared.append({"filename": s.get("filename", "Unknown"), "chunk_index": s.get("chunk_index", 0), "content": excerpt})
    return prepared


async def build_artifact(question: str, answer: str, sources: List[Dict[str, Any]], artifact_type: str = "auto") -> Dict[str, Any]:
    """Ask the first active MCP server exposing `generate_artifact` to build an artifact for a chat answer."""
    server = mcp_client_manager.find_server_with_tool(ARTIFACT_TOOL_NAME)
    if not server:
        return {
            "success": False,
            "error": f"No active MCP server exposes '{ARTIFACT_TOOL_NAME}'. Start mcp_servers/artifact_studio/server.py and refresh it in the MCP manager."
        }

    result = await mcp_client_manager.call_remote_tool(
        server_id=server["id"],
        tool_name=ARTIFACT_TOOL_NAME,
        arguments={
            "question": question,
            "answer": answer,
            "sources": _prepare_sources(question, answer, sources),
            "artifact_type": artifact_type
        }
    )
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "Artifact generation failed.")}

    artifact = result.get("result")
    if not isinstance(artifact, dict) or "type" not in artifact or "data" not in artifact:
        return {"success": False, "error": f"Server '{server['name']}' returned an invalid artifact."}

    return {"success": True, "server_id": server["id"], "server_name": server["name"], "artifact": artifact}
