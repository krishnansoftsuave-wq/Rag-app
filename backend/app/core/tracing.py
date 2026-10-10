"""
Per-request traces (Week 11): one JSON line per /chat request in logs/requests.jsonl, so any past answer can be
found from a vague complaint and replayed.

    with start_trace(mode="agent", user_id=..., query=...) as trace:
        with span("retrieval", stage="retrieval"):
            ...
        trace.set(answer=...)

Each span records its latency and the provider-reported tokens and cost of the LLM calls made inside it (via the
LLM client's usage meters). Spans may nest: a span's usage excludes the calls already counted by its child spans,
so summing every span's cost gives the request's cost exactly once. Stages are "retrieval", "generation" and "tool",
which is how cost_by_stage is split.

Outside a trace (tests, benchmarks, MCP tools) span() and record_contexts() do nothing.
"""
import itertools
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from app.core.config import BASE_DIR
from app.core.logger import get_logger

logger = get_logger("tracing")

TRACE_LOG_PATH = Path(os.getenv("TRACE_LOG_PATH", str(BASE_DIR / "logs" / "requests.jsonl")))
STAGES = ("retrieval", "generation", "tool")

_write_lock = threading.Lock()
_span_seq = itertools.count()  # creation order; time.time() is too coarse on Windows to order spans
_current_trace: ContextVar[Optional["RequestTrace"]] = ContextVar("current_trace", default=None)
_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)


# Cheap, deterministic input-type slice: the first rule whose pattern matches the question wins
_INPUT_TYPE_RULES = [
    ("code_sample", r"\b(code|sample|snippet|example|implement|write a|show me how|call|method|function|class|import|sdk|api)\b"),
    ("troubleshooting", r"\b(error|exception|fail|failing|broken|not working|bug|fix|issue|crash|timeout)\b"),
    ("how_to", r"\b(how (do|to|can|should)|steps?|configure|set ?up|install|enable)\b"),
    ("concept", r"\b(what is|what are|explain|why|difference|overview|meaning)\b"),
]


def classify_input(question: str) -> str:
    q = question.lower()
    return next((name for name, pattern in _INPUT_TYPE_RULES if re.search(pattern, q)), "other")


class Span:
    def __init__(self, name: str, stage: str, parent: Optional["Span"], attrs: Dict[str, Any]):
        self.span_id = uuid.uuid4().hex[:12]
        self.seq = next(_span_seq)
        self.parent_id = parent.span_id if parent else None
        self.name = name
        self.stage = stage
        self.attrs = dict(attrs)
        self.started_at = time.time()
        self.latency_ms = 0.0
        self.error: Optional[str] = None
        self.calls: List[Any] = []  # LLMCallUsage made in this span, minus those of child spans
        self._child_call_ids: set = set()

    def to_dict(self) -> Dict[str, Any]:
        from app.services.llm.pricing import call_cost
        calls = [{
            "label": c.label or None,
            "model": c.model,
            "input_tokens": c.input_tokens,
            "cached_input_tokens": c.cached_input_tokens,
            "output_tokens": c.output_tokens,
            "cost_usd": call_cost(c.model, c.input_tokens, c.cached_input_tokens, c.output_tokens),
        } for c in self.calls]
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "stage": self.stage,
            "start_offset_ms": None,  # filled in by the trace
            "latency_ms": round(self.latency_ms, 1),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "cached_input_tokens": sum(c["cached_input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "cost_usd": round(sum(c["cost_usd"] or 0.0 for c in calls), 8),
            "models": sorted({c["model"] for c in calls}),
            "llm_calls": calls,
            "attrs": self.attrs,
            "error": self.error,
        }


class RequestTrace:
    def __init__(self, fields: Dict[str, Any]):
        self.trace_id = uuid.uuid4().hex
        self.started_at = time.time()
        self.fields: Dict[str, Any] = dict(fields)
        self.spans: List[Span] = []
        self.contexts: Dict[str, Dict[str, Any]] = {}  # chunk_id -> retrieved context, in first-seen order
        self._lock = threading.Lock()

    def set(self, **fields: Any) -> None:
        """Add or replace top-level fields of the record (e.g. answer, prompt_version)."""
        with self._lock:
            self.fields.update(fields)

    def add_span(self, s: Span) -> None:
        with self._lock:
            self.spans.append(s)

    def add_contexts(self, contexts: Iterable[Dict[str, Any]], span_name: Optional[str]) -> None:
        with self._lock:
            for c in contexts:
                chunk_id = c["chunk_id"]
                if chunk_id not in self.contexts:
                    self.contexts[chunk_id] = {**c, "retrieved_by": span_name}

    def to_record(self, total_latency_ms: float, error: Optional[str]) -> Dict[str, Any]:
        spans = sorted(self.spans, key=lambda s: s.seq)
        span_dicts = []
        for s in spans:
            d = s.to_dict()
            d["start_offset_ms"] = round((s.started_at - self.started_at) * 1000, 1)
            span_dicts.append(d)

        stage_cost = {stage: 0.0 for stage in STAGES}
        stage_latency = {stage: 0.0 for stage in STAGES}
        for d in span_dicts:
            stage_cost[d["stage"]] = stage_cost.get(d["stage"], 0.0) + d["cost_usd"]
            if d["parent_id"] is None:  # nested spans overlap their parent in time
                stage_latency[d["stage"]] = stage_latency.get(d["stage"], 0.0) + d["latency_ms"]

        input_tokens = sum(d["input_tokens"] for d in span_dicts)
        output_tokens = sum(d["output_tokens"] for d in span_dicts)
        answer = self.fields.get("answer") or ""
        record = {
            "trace_id": self.trace_id,
            "timestamp": datetime.fromtimestamp(self.started_at, tz=timezone.utc).isoformat(timespec="milliseconds"),
            **{k: v for k, v in self.fields.items() if k != "answer"},
            "answer": answer,
            "answer_chars": len(answer),
            "answer_has_code": "```" in answer,
            "retrieved_context": list(self.contexts.values()),
            "context_ids": [c["chunk_id"] for c in self.contexts.values()],
            "spans": span_dicts,
            "totals": {
                "latency_ms": round(total_latency_ms, 1),
                "llm_calls": sum(len(d["llm_calls"]) for d in span_dicts),
                "input_tokens": input_tokens,
                "cached_input_tokens": sum(d["cached_input_tokens"] for d in span_dicts),
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost_usd": round(sum(stage_cost.values()), 8),
            },
            "cost_by_stage": {k: round(v, 8) for k, v in stage_cost.items()},
            "latency_by_stage_ms": {k: round(v, 1) for k, v in stage_latency.items()},
            "models": sorted({m for d in span_dicts for m in d["models"]}),
            "status": "error" if error else "ok",
            "error": error,
        }
        return record


def current_trace() -> Optional[RequestTrace]:
    return _current_trace.get()


@contextmanager
def start_trace(**fields: Any) -> Iterator[RequestTrace]:
    """Trace one request; its record is appended to TRACE_LOG_PATH when the block exits, also on error."""
    trace = RequestTrace(fields)
    token = _current_trace.set(trace)
    span_token = _current_span.set(None)
    error = None
    try:
        yield trace
    except BaseException as err:
        error = f"{type(err).__name__}: {err}"
        raise
    finally:
        _current_span.reset(span_token)
        _current_trace.reset(token)
        _write(trace.to_record((time.time() - trace.started_at) * 1000, error))


@contextmanager
def span(name: str, stage: str, **attrs: Any) -> Iterator[Optional[Span]]:
    """Time a step of the current request and meter the LLM calls made inside it. No-op outside a trace."""
    trace = _current_trace.get()
    if trace is None:
        yield None
        return
    # Imported here: app.services imports this module while it is being initialised
    from app.services.llm.client import track_usage
    parent = _current_span.get()
    s = Span(name, stage, parent, attrs)
    token = _current_span.set(s)
    try:
        with track_usage() as meter:
            yield s
    except BaseException as err:
        s.error = f"{type(err).__name__}: {err}"
        raise
    finally:
        _current_span.reset(token)
        s.latency_ms = (time.time() - s.started_at) * 1000
        with trace._lock:
            s.calls = [c for c in meter.calls if id(c) not in s._child_call_ids]
            if parent is not None:
                parent._child_call_ids.update(id(c) for c in meter.calls)
        trace.add_span(s)


def context_id(doc_id: str, chunk_index: Any) -> str:
    """Stable id of a retrieved chunk: <doc_id>#<chunk_index>."""
    return f"{doc_id}#{chunk_index}"


def record_contexts(citations: Iterable[Any]) -> List[str]:
    """Log retrieved chunks (SourceCitation objects or evidence dicts) on the current trace and current span.
    Returns their context ids."""
    trace = _current_trace.get()
    rows = []
    for c in citations:
        get = (lambda k, d=None: c.get(k, d)) if isinstance(c, dict) else (lambda k, d=None: getattr(c, k, d))
        content = get("content") or get("full_content") or get("snippet") or ""
        rows.append({
            "chunk_id": context_id(get("doc_id", ""), get("chunk_index", 0)),
            "doc_id": get("doc_id", ""),
            "filename": get("filename", "Unknown"),
            "chunk_index": get("chunk_index", 0),
            "score": round(float(get("score", 0.0) or 0.0), 4),
            "preview": content[:160],
        })
    ids = [r["chunk_id"] for r in rows]
    if trace is not None:
        s = _current_span.get()
        trace.add_contexts(rows, s.name if s else None)
        if s is not None:
            s.attrs.setdefault("context_ids", [])
            s.attrs["context_ids"] += [i for i in ids if i not in s.attrs["context_ids"]]
    return ids


def _write(record: Dict[str, Any]) -> None:
    try:
        TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _write_lock, open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        logger.info(
            f"trace_id={record['trace_id']} mode={record.get('mode')} status={record['status']} "
            f"latency_ms={record['totals']['latency_ms']} tokens={record['totals']['total_tokens']} "
            f"cost=${record['totals']['cost_usd']:.6f} prompt_version={record.get('prompt_version')}"
        )
    except Exception as err:  # logging must never break a request
        logger.error(f"Could not write trace record: {err}")
