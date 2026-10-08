import json
import time
import math
import re
from typing import Dict, Any, List, Optional
from app.services import hybrid_retriever_service, llm_service
from app.schemas.chat import SourceCitation
from app.core.config import DEFAULT_TOP_K
from app.services.llm.client import complete


def estimate_tokens(text: str) -> int:
    """Rough token count estimation (~4 characters per token)."""
    return max(1, len(str(text))) // 4 + 1


def semantic_vector_search(
    query: str,
    document_id: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K
) -> Dict[str, Any]:
    """
    TOOL: semantic_vector_search
    Description: Retrieve document chunks using dense semantic vector search (embedding similarity).
    Best used for: Conceptual, semantic, or open-ended user questions.
    """
    doc_ids = [document_id] if (document_id and document_id != "test_kb") else None
    citations: List[SourceCitation] = hybrid_retriever_service.retrieve_context(
        query=query,
        doc_ids=doc_ids,
        top_k=top_k,
        search_mode="vector"
    )

    results = []
    top_score = 0.0
    for idx, c in enumerate(citations):
        score = float(c.score)
        if idx == 0:
            top_score = score
        results.append({
            "chunk_index": c.chunk_index,
            "filename": c.filename,
            "doc_id": c.doc_id,
            "score": score,
            "snippet": c.content[:300] if len(c.content) > 300 else c.content,
            "full_content": c.content
        })

    return {
        "tool": "semantic_vector_search",
        "results": results,
        "result_count": len(results),
        "top_score": round(top_score, 4),
        "query": query
    }


def exact_keyword_search(
    query: str,
    document_id: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K
) -> Dict[str, Any]:
    """
    TOOL: exact_keyword_search
    Description: Retrieve document chunks using BM25 sparse keyword search.
    Best used for: Specific code names, exact model numbers, error codes, dates, or technical jargon.
    """
    doc_ids = [document_id] if (document_id and document_id != "test_kb") else None
    citations: List[SourceCitation] = hybrid_retriever_service.retrieve_context(
        query=query,
        doc_ids=doc_ids,
        top_k=top_k,
        search_mode="bm25"
    )

    results = []
    top_score = 0.0
    for idx, c in enumerate(citations):
        score = float(c.score)
        if idx == 0:
            top_score = score
        results.append({
            "chunk_index": c.chunk_index,
            "filename": c.filename,
            "doc_id": c.doc_id,
            "score": score,
            "snippet": c.content[:300] if len(c.content) > 300 else c.content,
            "full_content": c.content
        })

    return {
        "tool": "exact_keyword_search",
        "results": results,
        "result_count": len(results),
        "top_score": round(top_score, 4),
        "query": query
    }


def python_calculator(expression: str) -> Dict[str, Any]:
    """
    TOOL: python_calculator
    Description: Safely evaluate mathematical expressions (e.g. percentages, ratios, budget totals, differences).
    Best used for: Any math calculation requested by the user or required during evidence analysis.
    """
    try:
        # Sanitize input expression for safe math evaluation
        clean_expr = re.sub(r'[^0-9\+\-\*\/\%\(\)\.\s,]', '', expression)
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "math": math
        }
        val = eval(clean_expr, {"__builtins__": None}, allowed_names)
        return {
            "tool": "python_calculator",
            "expression": expression,
            "evaluated_result": val,
            "success": True
        }
    except Exception as err:
        return {
            "tool": "python_calculator",
            "expression": expression,
            "error": str(err),
            "success": False
        }


def summarize_context(text: str, focus_topic: Optional[str] = None) -> Dict[str, Any]:
    """
    TOOL: summarize_context
    Description: Summarize large context passages or extract specific key facts focused on a topic.
    Best used for: Distilling verbose retrieved evidence into concise bullet points.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if focus_topic:
        topic_words = [w.lower() for w in focus_topic.split() if len(w) > 2]
        matching_lines = [l for l in lines if any(w in l.lower() for w in topic_words)]
        summary_text = "\n".join(matching_lines[:5]) if matching_lines else "\n".join(lines[:5])
    else:
        summary_text = "\n".join(lines[:5])

    return {
        "tool": "summarize_context",
        "focus_topic": focus_topic,
        "summary": summary_text,
        "bullet_count": min(len(lines), 5)
    }


def agentic_document_chunker(full_text: str) -> Dict[str, Any]:
    """
    TOOL: agentic_document_chunker
    Description: Perform proposition-based agentic chunking on raw document text to split it into semantically coherent spans.
    Best used for: Chunking or restructuring unformatted text documents into optimal passages for RAG retrieval.
    """
    try:
        from app.services import agentic_chunker_service, hybrid_retriever_service
        spans_data = agentic_chunker_service.chunk_text_agentically(
            full_text=full_text,
            embedding_model=hybrid_retriever_service.embedding_model
        )
        return {
            "tool": "agentic_document_chunker",
            "total_chunks": len(spans_data),
            "chunks": [s["content"] for s in spans_data[:10]],
            "success": True
        }
    except Exception as err:
        return {
            "tool": "agentic_document_chunker",
            "error": str(err),
            "success": False
        }


def search_document(
    document_id: Optional[str] = None,
    query: str = "",
    top_k: int = DEFAULT_TOP_K
) -> Dict[str, Any]:
    """
    TOOL: search_document (Hybrid Search)
    Description: Retrieve document chunks combining vector embedding and BM25 keyword search via Reciprocal Rank Fusion (RRF).
    """
    doc_ids = [document_id] if (document_id and document_id != "test_kb") else None
    citations: List[SourceCitation] = hybrid_retriever_service.retrieve_context(
        query=query,
        doc_ids=doc_ids,
        top_k=top_k,
        search_mode="hybrid"
    )

    results = []
    top_score = 0.0
    for idx, c in enumerate(citations):
        score = float(c.score)
        if idx == 0:
            top_score = score
        results.append({
            "chunk_index": c.chunk_index,
            "filename": c.filename,
            "doc_id": c.doc_id,
            "score": score,
            "snippet": c.content[:300] if len(c.content) > 300 else c.content,
            "full_content": c.content
        })

    return {
        "tool": "search_document",
        "results": results,
        "result_count": len(results),
        "top_score": round(top_score, 4),
        "query": query
    }


def refine_document_search(
    document_id: Optional[str] = None,
    query: str = "",
    top_k: int = DEFAULT_TOP_K
) -> Dict[str, Any]:
    """
    TOOL: refine_document_search
    Description: Perform targeted follow-up search based on a identified missing information gap.
    """
    res = search_document(document_id=document_id, query=query, top_k=top_k)
    res["refined_query"] = query
    res["tool"] = "refine_document_search"
    return res


def validate_evidence(
    question: str,
    retrieved_context: str,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    TOOL: validate_evidence
    Description: Determine whether retrieved context is sufficient to fully answer the question.
    """
    if not retrieved_context or not retrieved_context.strip():
        return {
            "sufficient": False,
            "reason": "No document evidence was retrieved.",
            "missing_information": [question],
            "input_tokens": estimate_tokens(question + (retrieved_context or "")),
            "output_tokens": 30
        }

    prompt = f"""You are an objective evidence auditor for a RAG system.
Evaluate if the Provided Context contains sufficient information to directly answer the User Question.

User Question: {question}

Provided Context:
{retrieved_context}

Respond in strict JSON format:
{{
    "sufficient": true/false,
    "reason": "Clear, concise reason",
    "missing_information": ["specific topic or detail missing", ...]
}}
JSON Response:"""

    input_tokens = estimate_tokens(prompt)

    # An LLM is required: raises LLMUnavailableError when no model can answer
    text, model_name = complete(prompt, api_key=api_key, json_mode=True)
    output_tokens = estimate_tokens(text)
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        data = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        return {
            "sufficient": False,
            "reason": f"Model {model_name} returned an unreadable validation result.",
            "missing_information": [question],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }
    return {
        "sufficient": bool(data.get("sufficient", False)),
        "reason": str(data.get("reason", f"Evaluated via {model_name}")),
        "missing_information": list(data.get("missing_information", [])),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }


# Central registry of tool functions for dynamic LLM dispatching
REGISTERED_TOOLS: Dict[str, Any] = {
    "semantic_vector_search": semantic_vector_search,
    "exact_keyword_search": exact_keyword_search,
    "python_calculator": python_calculator,
    "summarize_context": summarize_context,
    "agentic_document_chunker": agentic_document_chunker,
    "search_document": search_document,
    "refine_document_search": refine_document_search,
    "validate_evidence": validate_evidence,
}

# Functions exported to Gemini Client for tool injection
EXPOSED_TOOL_FUNCTIONS = [
    search_document,
    refine_document_search,
    semantic_vector_search,
    exact_keyword_search,
    python_calculator,
    summarize_context,
    agentic_document_chunker,
    validate_evidence,
]


