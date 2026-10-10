"""
Fill logs/requests.jsonl with a week of background traffic for the support drill, so the planted bad answer has to
be found among thousands of requests instead of a handful.

The records are synthetic (real requests would use up the Groq free-tier tokens) and carry "synthetic": true. They
have the same shape as real traces: users, sessions, input types, modes, answers with and without code samples
(using the current 3.x SDK methods), retrieved context ids, spans and costs drawn around the measured per-mode
costs. They are written in time order, interleaved with any real records already in the log.

  python scripts/seed_traffic.py --count 2000 --days 7 --seed 11
"""
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "requests.jsonl"

QUESTIONS = {
    "code_sample": [
        ("Show me how to download an object with the Python SDK", "```python\nfrom novacloud import Client\nclient = Client(api_key=KEY)\nclient.objects.download(\"my-bucket\", \"{k}\", \"./{k}\")\n```"),
        ("Give me a code example to create a client", "```python\nfrom novacloud import Client\nclient = Client(api_key=\"YOUR_API_KEY\", region=\"{r}\")\n```"),
        ("Python snippet to upload a file with metadata", "```python\nclient.objects.upload(\"my-bucket\", \"{k}\", \"{k}\", metadata={{\"owner\": \"{u}\"}})\n```"),
        ("How do I call the Objects API to upload a large video?", "Use the streaming upload:\n```python\nclient.objects.upload(\"media\", \"{k}\", open(\"{k}\", \"rb\"))\n```"),
        ("Write code to list objects in a bucket", "```python\nfor obj in client.objects.list(\"my-bucket\"):\n    print(obj.key)\n```"),
    ],
    "concept": [
        ("What is the difference between NovaSQL and NovaDocument?", "NovaSQL is relational and transactional; NovaDocument stores flexible JSON-like documents without joins."),
        ("What is RPO?", "RPO is the maximum acceptable amount of data loss measured in time."),
        ("Explain NovaObject storage classes", "Standard, Infrequent Access and Archive trade storage price against retrieval cost."),
        ("What are availability zones?", "Each region has several zones; spreading workloads across two or more reduces the impact of failures."),
    ],
    "how_to": [
        ("How do I configure backup retention for NovaSQL?", "Set retention between 7 and 35 days in the database settings."),
        ("How to enable cross-region replication on a bucket?", "Enable replication on the bucket and pick a destination region; replication is asynchronous."),
        ("How can I set up an alert on CPU usage?", "Create a NovaMetrics alert, for example CPU above 80% for five minutes."),
    ],
    "troubleshooting": [
        ("Why does my upload fail with error 403?", "The API key cannot write to the bucket; check its role."),
        ("My function times out after 15 minutes, why?", "NovaFunction executions are capped at 15 minutes."),
        ("Getting AttributeError on client.objects, what is wrong?", "You are on SDK 2.x; client.objects exists from 3.0."),
    ],
    "other": [
        ("hi", "Hello! Ask me anything about the documents you uploaded."),
        ("thanks", "You're welcome."),
    ],
}
INPUT_TYPE_WEIGHTS = {"code_sample": 30, "concept": 25, "how_to": 20, "troubleshooting": 15, "other": 10}
MODES = {"agent": (70, 0.0051, 9000), "standard": (20, 0.0009, 5000), "team": (7, 0.0090, 14000), "workflow": (3, 0.0015, 6000)}
DOCS = ["novacloud_sdk_v3_reference", "novacloud_eval_doc", "w10_novacloud", "ed046646", "eval_late_5bdc"]
FILES = {"novacloud_sdk_v3_reference": "novacloud_sdk_v3_reference.md", "novacloud_eval_doc": "NovaCloud_RAG_Evaluation_Document.txt",
         "w10_novacloud": "novacloud_w10.pdf", "ed046646": "novacloud_rag_test_document.pdf", "eval_late_5bdc": "eval_late.txt"}
USERS = [f"u_{i:03d}" for i in range(1, 41)]


def make_record(ts: datetime, rng: random.Random) -> dict:
    input_type = rng.choices(list(INPUT_TYPE_WEIGHTS), weights=list(INPUT_TYPE_WEIGHTS.values()))[0]
    question, template = rng.choice(QUESTIONS[input_type])
    mode = rng.choices(list(MODES), weights=[m[0] for m in MODES.values()])[0]
    _, mean_cost, mean_ms = MODES[mode]
    cost = max(0.0001, rng.lognormvariate(0, 0.35) * mean_cost)
    latency = max(800.0, rng.lognormvariate(0, 0.3) * mean_ms)
    answer = template.format(k=rng.choice(["report.pdf", "q3.csv", "intro.mp4", "logo.png"]),
                             r=rng.choice(["us-east", "eu-central"]), u=rng.choice(USERS))
    retrieval_share = rng.uniform(0.1, 0.25)
    contexts = []
    for _ in range(rng.randint(2, 6)):
        doc = rng.choice(DOCS)
        idx = rng.randint(0, 14)
        contexts.append({"chunk_id": f"{doc}#{idx}", "doc_id": doc, "filename": FILES[doc], "chunk_index": idx,
                         "score": round(rng.uniform(0.3, 1.0), 4), "preview": "", "retrieved_by": "retrieval"})
    in_tok = int(cost / 0.0000003 * 0.85)
    out_tok = int(in_tok * rng.uniform(0.1, 0.25))
    span_rows = [
        {"name": "retrieval", "stage": "retrieval", "latency_ms": round(latency * 0.3, 1), "cost_usd": round(cost * retrieval_share, 8)},
        {"name": "generate_answer" if mode != "agent" else "agent_llm_step", "stage": "generation",
         "latency_ms": round(latency * 0.7, 1), "cost_usd": round(cost * (1 - retrieval_share), 8)},
    ]
    return {
        "trace_id": uuid.UUID(int=rng.getrandbits(128)).hex,
        "timestamp": ts.isoformat(timespec="milliseconds"),
        "synthetic": True,
        "mode": mode,
        "user_id": rng.choice(USERS),
        "username": None,
        "session_id": f"chat_{rng.getrandbits(32):08x}",
        "prompt_version": "rag-v1.0",
        "query": question,
        "input_type": input_type,
        "doc_ids": None,
        "search_mode": "hybrid",
        "termination_reason": "completed",
        "system_answers": None,
        "answer": answer,
        "answer_chars": len(answer),
        "answer_has_code": "```" in answer,
        "retrieved_context": contexts,
        "context_ids": [c["chunk_id"] for c in contexts],
        "spans": span_rows,
        "totals": {"latency_ms": round(latency, 1), "llm_calls": rng.randint(2, 12), "input_tokens": in_tok,
                   "cached_input_tokens": 0, "output_tokens": out_tok, "total_tokens": in_tok + out_tok,
                   "cost_usd": round(cost, 8)},
        "cost_by_stage": {"retrieval": round(cost * retrieval_share, 8), "generation": round(cost * (1 - retrieval_share), 8), "tool": 0.0},
        "latency_by_stage_ms": {"retrieval": round(latency * 0.3, 1), "generation": round(latency * 0.7, 1), "tool": 0.0},
        "models": ["openai/gpt-oss-120b"],
        "status": "ok",
        "error": None,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p.add_argument("--count", type=int, default=2000)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()

    rng = random.Random(a.seed)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=a.days)
    seeded = [make_record(start + timedelta(seconds=rng.uniform(0, a.days * 86400)), rng) for _ in range(a.count)]

    existing = []
    if a.log.exists():
        existing = [json.loads(line) for line in a.log.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = sorted(existing + seeded, key=lambda r: r["timestamp"])
    a.log.parent.mkdir(parents=True, exist_ok=True)
    with open(a.log, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{a.log}: {len(existing)} existing + {len(seeded)} synthetic records over {a.days} days")


if __name__ == "__main__":
    main()
