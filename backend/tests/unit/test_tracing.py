"""Request traces: spans meter their own LLM calls (not their children's), and each request writes one JSON line."""
import json

from app.core import tracing
from app.core.tracing import classify_input, record_contexts, span, start_trace
from app.services.llm import client
from app.services.llm.client import LLMCallUsage


def _fake_llm_call(input_tokens: int, output_tokens: int, model: str = "openai/gpt-oss-120b") -> None:
    """What client._metered does after a successful call: add the provider-reported usage to every active meter."""
    call = LLMCallUsage("", model, input_tokens, 0, output_tokens)
    for meter in client._meters.get():
        meter.add(call)


def _read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_trace_record_has_spans_costs_and_contexts(tmp_path, monkeypatch):
    log = tmp_path / "requests.jsonl"
    monkeypatch.setattr(tracing, "TRACE_LOG_PATH", log)

    with start_trace(mode="agent", user_id="u1", query="show me a code sample", prompt_version="rag-v1.0") as trace:
        with span("tool:semantic_vector_search", stage="retrieval"):
            with span("retrieval", stage="retrieval"):
                _fake_llm_call(100, 20)  # query expansion
                record_contexts([{"doc_id": "d1", "chunk_index": 3, "filename": "sdk.md", "score": 0.9,
                                  "full_content": "client.connect()"}])
        with span("generate_answer", stage="generation"):
            _fake_llm_call(1000, 200)
        trace.set(answer="```python\nclient.connect()\n```")

    [rec] = _read_records(log)
    assert rec["trace_id"] == trace.trace_id
    assert rec["user_id"] == "u1" and rec["prompt_version"] == "rag-v1.0"
    assert rec["answer_has_code"] is True
    assert rec["context_ids"] == ["d1#3"]
    assert rec["retrieved_context"][0]["retrieved_by"] == "retrieval"

    spans = {s["name"]: s for s in rec["spans"]}
    # The wrapping tool span does not count its child's LLM call again
    assert spans["tool:semantic_vector_search"]["input_tokens"] == 0
    assert spans["retrieval"]["input_tokens"] == 100
    assert spans["retrieval"]["parent_id"] == spans["tool:semantic_vector_search"]["span_id"]
    assert spans["generate_answer"]["output_tokens"] == 200

    # gpt-oss-120b: $0.15 in / $0.60 out per 1M tokens
    retrieval_cost = (100 * 0.15 + 20 * 0.60) / 1e6
    generation_cost = (1000 * 0.15 + 200 * 0.60) / 1e6
    assert abs(rec["cost_by_stage"]["retrieval"] - retrieval_cost) < 1e-12
    assert abs(rec["cost_by_stage"]["generation"] - generation_cost) < 1e-12
    assert abs(rec["totals"]["cost_usd"] - (retrieval_cost + generation_cost)) < 1e-12
    assert rec["totals"]["total_tokens"] == 1320


def test_failed_request_is_still_logged(tmp_path, monkeypatch):
    log = tmp_path / "requests.jsonl"
    monkeypatch.setattr(tracing, "TRACE_LOG_PATH", log)
    try:
        with start_trace(mode="agent", query="q"):
            with span("generate_answer", stage="generation"):
                raise RuntimeError("model down")
    except RuntimeError:
        pass
    [rec] = _read_records(log)
    assert rec["status"] == "error" and "model down" in rec["error"]
    assert rec["spans"][0]["error"].startswith("RuntimeError")


def test_span_outside_a_trace_is_a_no_op():
    with span("retrieval", stage="retrieval") as s:
        assert s is None
    assert record_contexts([{"doc_id": "d", "chunk_index": 0}]) == ["d#0"]


def test_classify_input():
    assert classify_input("Give me a code sample to upload a file") == "code_sample"
    assert classify_input("Why does the upload fail with error 413?") == "troubleshooting"
    assert classify_input("What is a bucket?") == "concept"
