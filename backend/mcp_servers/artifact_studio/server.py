import os
import re
import json
import uuid
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# Load backend/.env (two levels up) no matter which directory the server is started from
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Same provider choice as the backend: LLM_PROVIDER, else Groq when GROQ_API_KEY is set, else Gemini
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PROVIDER = (os.getenv("LLM_PROVIDER") or ("groq" if GROQ_API_KEY else "gemini")).strip().lower()
PROVIDER_LABEL = {"groq": "Groq", "gemini": "Gemini"}.get(PROVIDER, PROVIDER)
API_KEY = GROQ_API_KEY if PROVIDER == "groq" else GEMINI_API_KEY
CANDIDATE_MODELS = {
    "groq": [m.strip() for m in os.getenv("GROQ_MODELS", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()],
    "gemini": ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
}.get(PROVIDER, [])
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
LLM_TIMEOUT_SECONDS = 15  # per model attempt
LLM_TOTAL_BUDGET_SECONDS = 30  # across all models
# A model that is rate-limited, overloaded or slow is skipped for a while instead of retried every call
LLM_ERROR_RULES = [
    ("RESOURCE_EXHAUSTED", 300, "quota exceeded (429)"), ("rate_limit", 60, "rate limit reached (429)"),
    ("429", 120, "rate limit reached (429)"),
    ("UNAVAILABLE", 60, "model overloaded (503)"), ("503", 60, "model overloaded (503)"),
    ("TimeoutError", 60, "request timed out"), ("Timeout", 60, "request timed out"),
    ("model_not_found", 3600, "model not found (404)"), ("NOT_FOUND", 3600, "model not found (404)"),
    ("404", 3600, "model not found (404)"),
]
_model_cooldown_until: Dict[str, float] = {}

ARTIFACT_TYPES = {
    "key_points": "Numbered key findings with a short summary, each tied to its source file.",
    "table": "Rows and columns for comparisons, lists of items, or multi-attribute facts.",
    "timeline": "Chronological events for questions about dates, history, milestones, or schedules.",
    "chart": "Bar chart of comparable numeric values (metrics, amounts, percentages).",
    "mindmap": "Central topic with branches and sub-points for overviews and topic structure.",
}
TYPE_LABELS = {"key_points": "Key Points", "table": "Table", "timeline": "Timeline", "chart": "Chart", "mindmap": "Mind Map"}

MAX_SOURCES = 8
MAX_SOURCE_CHARS = 2000  # the backend already sends focused excerpts of long chunks within this size

# Initialize Standalone FastMCP Server
# The instructions are this server's self-description: clients read them on connect to decide when to use it
standalone_mcp = FastMCP(
    "DocuBrain-Artifact-Studio",
    instructions=(
        "Creates visual artifacts from document content: charts and graphs of numbers, comparison tables, "
        "timelines of dates and events, mind maps of topics, and key-point summaries. Use it when the user wants "
        "to see information visually or in a structured format, not for plain questions."
    ),
)


def _shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", re.sub(r"[*_`#>|]+", " ", text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------------------
# LLM builder (required: there is no non-LLM fallback)
# ---------------------------------------------------------------------------

ARTIFACT_PROMPT = """You build a visual artifact that accompanies an answer in a document Q&A app.
Use ONLY facts found in the source passages. Never invent numbers, dates or names.

Pick the artifact type that best presents the answer{type_rule}:
- key_points: {{"summary": str, "points": [{{"text": str, "source": filename}}]}}  (3-7 points)
- table: {{"columns": [str], "rows": [[str]]}}  (every row has one cell per column, max 12 rows)
- timeline: {{"events": [{{"date": str, "title": str, "detail": str, "source": filename}}]}}  (chronological)
- chart: {{"unit": str, "series": [{{"label": str, "value": number}}]}}  (only comparable numbers sharing one unit, 2-10 bars)
- mindmap: {{"root": str, "branches": [{{"label": str, "children": [str]}}]}}  (3-6 branches, 1-4 short children each)

Return JSON only, shaped as:
{{"type": "<type>", "title": "<max 80 chars>", "description": "<one sentence>", "data": <shape for that type>}}

Question: {question}

Answer given to the user:
{answer}

Source passages:
{context}
"""


def _llm_client() -> Any:
    if PROVIDER == "groq":
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=API_KEY, base_url=GROQ_BASE_URL, max_retries=0)
    from google import genai
    return genai.Client(api_key=API_KEY)


async def _request_json(client: Any, model_name: str, prompt: str) -> str:
    """One JSON-mode completion from the configured provider."""
    if PROVIDER == "groq":
        res = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return res.choices[0].message.content or ""
    res = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "automatic_function_calling": {"disable": True},
        },
    )
    return res.text or ""


async def _llm_artifact(question: str, answer: str, sources: List[Dict[str, Any]], requested: str) -> Dict[str, Any]:
    """Build the artifact with the configured LLM, or raise ToolError explaining why it could not."""
    if not API_KEY:
        key_var = "GROQ_API_KEY" if PROVIDER == "groq" else "GEMINI_API_KEY"
        raise ToolError(f"No {PROVIDER_LABEL} API key configured for the artifact server. Set {key_var} in backend/.env.")

    context = "\n\n".join(
        f"[{i}] File: {s.get('filename', 'Unknown')}\n{str(s.get('content', ''))[:MAX_SOURCE_CHARS]}"
        for i, s in enumerate(sources, 1)
    )
    type_rule = f" (you MUST use type \"{requested}\")" if requested in ARTIFACT_TYPES else ""
    prompt = ARTIFACT_PROMPT.format(type_rule=type_rule, question=question, answer=answer[:3000], context=context)

    client = _llm_client()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + LLM_TOTAL_BUDGET_SECONDS
    last_error = "every model is cooling down after recent failures"
    for model_name in CANDIDATE_MODELS:
        if _model_cooldown_until.get(model_name, 0) > time.time():
            continue
        remaining = deadline - loop.time()
        if remaining < 2:
            last_error = f"no model answered within {LLM_TOTAL_BUDGET_SECONDS}s"
            break
        try:
            text = await asyncio.wait_for(_request_json(client, model_name, prompt), timeout=min(LLM_TIMEOUT_SECONDS, remaining))
            parsed = json.loads(text)
            if isinstance(parsed, dict) and _validate(parsed.get("type"), parsed.get("data")):
                parsed["generated_by"] = f"{PROVIDER}:{model_name}"
                return parsed
            last_error = f"{model_name}: returned an unusable artifact"
        except Exception as err:
            message = f"{type(err).__name__}: {err}"
            rule = next(((secs, reason) for marker, secs, reason in LLM_ERROR_RULES if marker in message), None)
            if rule:
                _model_cooldown_until[model_name] = time.time() + rule[0]
            last_error = f"{model_name}: {rule[1] if rule else message[:160]}"
        print(f"[Artifact Studio] {last_error}")
    raise ToolError(f"{PROVIDER_LABEL} could not build the artifact (last error: {last_error}).")


def _validate(artifact_type: Any, data: Any) -> bool:
    if artifact_type not in ARTIFACT_TYPES or not isinstance(data, dict):
        return False
    if artifact_type == "key_points":
        return isinstance(data.get("points"), list) and len(data["points"]) > 0
    if artifact_type == "table":
        cols, rows = data.get("columns"), data.get("rows")
        return isinstance(cols, list) and len(cols) > 0 and isinstance(rows, list) and len(rows) > 0 \
            and all(isinstance(r, list) for r in rows)
    if artifact_type == "timeline":
        return isinstance(data.get("events"), list) and len(data["events"]) > 0
    if artifact_type == "chart":
        series = data.get("series")
        return isinstance(series, list) and len(series) >= 2 \
            and all(isinstance(p, dict) and isinstance(p.get("value"), (int, float)) for p in series)
    if artifact_type == "mindmap":
        return isinstance(data.get("branches"), list) and len(data["branches"]) > 0
    return False


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def _to_markdown(artifact: Dict[str, Any]) -> str:
    t, d = artifact["type"], artifact["data"]
    lines = [f"# {artifact['title']}", "", artifact.get("description", ""), ""]
    if t == "key_points":
        if d.get("summary"):
            lines += [d["summary"], ""]
        lines += [f"{i}. {p.get('text', '')}" + (f" _({p['source']})_" if p.get("source") else "")
                  for i, p in enumerate(d.get("points", []), 1)]
    elif t == "table":
        cols = [str(c) for c in d.get("columns", [])]
        lines += ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(str(c).replace("|", "/") for c in row) + " |" for row in d.get("rows", [])]
    elif t == "timeline":
        lines += [f"- **{e.get('date', '')}**: {e.get('title', '')}. {e.get('detail', '')}" for e in d.get("events", [])]
    elif t == "chart":
        unit = d.get("unit", "")
        lines += ["| Label | Value |", "|---|---|"]
        lines += [f"| {p.get('label', '')} | {p.get('value', '')}{(' ' + unit) if unit else ''} |" for p in d.get("series", [])]
    elif t == "mindmap":
        lines += [f"- **{d.get('root', '')}**"]
        for b in d.get("branches", []):
            lines.append(f"  - {b.get('label', '')}")
            lines += [f"    - {c}" for c in b.get("children", [])]
    sources = artifact.get("source_files") or []
    if sources:
        lines += ["", "**Sources:** " + ", ".join(sources)]
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@standalone_mcp.tool()
async def generate_artifact(
    question: str,
    answer: str = "",
    sources: Optional[List[Dict[str, Any]]] = None,
    artifact_type: str = "auto",
) -> Dict[str, Any]:
    """
    Create a visual artifact from the retrieved document passages. Use it only when the user asks to see
    information visually or in a structured format: a chart or graph (comparable numbers), a table
    (comparison or list), a timeline (dates, history), a mind map (overview of topics) or a key-points summary.
    Do not use it for plain questions. Content comes only from the supplied sources.
    Args:
        question: The user's request, e.g. "Show the storage tier prices as a chart"
        answer: The answer DocuBrain returned, if any
        sources: Retrieved chunks, each {"filename": str, "content": str, "chunk_index": int}
        artifact_type: chart, table, timeline, mindmap or key_points when the user asked for one; otherwise "auto"
    """
    sources = [s for s in (sources or []) if isinstance(s, dict) and s.get("content")][:MAX_SOURCES]
    if not sources:
        raise ToolError("No source passages supplied; an artifact needs retrieved document context.")
    requested = (artifact_type or "auto").strip().lower()

    artifact = await _llm_artifact(question, answer, sources, requested)
    artifact["title"] = _shorten(artifact.get("title") or f"{TYPE_LABELS[artifact['type']]}: {question}", 80)
    artifact["description"] = _shorten(
        artifact.get("description") or f"Built from {len(sources)} retrieved passage(s) for: {question}", 200
    )
    artifact["artifact_id"] = f"art_{uuid.uuid4().hex[:8]}"
    artifact["source_files"] = sorted({s.get("filename", "Unknown") for s in sources})
    artifact["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    artifact["markdown"] = _to_markdown(artifact)
    return artifact


@standalone_mcp.tool()
def list_artifact_types() -> Dict[str, Any]:
    """
    List the visual formats generate_artifact can create. Use only when the user asks which chart, table or
    diagram formats are available.
    """
    return {
        "types": [{"type": k, "description": v} for k, v in ARTIFACT_TYPES.items()],
        "llm_provider": PROVIDER,
        "api_key_configured": bool(API_KEY),
    }


if __name__ == "__main__":
    print("=========================================================================")
    print("Starting DocuBrain Artifact Studio MCP Server on http://localhost:8005/sse")
    print("   Tools: generate_artifact, list_artifact_types")
    print(f"   LLM: {PROVIDER_LABEL} ({', '.join(CANDIDATE_MODELS)}), API key: {'configured' if API_KEY else 'MISSING (generate_artifact will return errors)'}")
    print("=========================================================================")

    # FastMCP SSE runner on port 8005
    standalone_mcp.run(transport="sse", host="127.0.0.1", port=8005)
