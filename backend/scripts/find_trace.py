"""
Find past requests in logs/requests.jsonl (the support drill). Slices can be combined; text search covers the
generated answer as well as the question, because complaints usually describe the output.

  python scripts/find_trace.py --text "connect_legacy" --since 7d          # search answers, questions, contexts
  python scripts/find_trace.py --text "upload" --in answer --code-only     # only answers that contain code
  python scripts/find_trace.py --user u_42 --since 2026-10-01 --until 2026-10-08
  python scripts/find_trace.py --prompt-version rag-v1.0 --input-type code_sample
  python scripts/find_trace.py --cost-outliers                             # requests above the p95 cost
  python scripts/find_trace.py --stats                                     # counts and cost per slice
  python scripts/find_trace.py --show 3f9a2c --out trace.json              # one full trace (id prefix ok)
"""
import argparse
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "requests.jsonl"


def load(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"warning: skipping malformed line {n}", file=sys.stderr)


def parse_time(value: str) -> datetime:
    """'7d', '24h', '30m' (ago) or an ISO date/time (UTC if no offset)."""
    rel = re.fullmatch(r"(\d+)([dhm])", value)
    if rel:
        unit = {"d": "days", "h": "hours", "m": "minutes"}[rel.group(2)]
        return datetime.now(timezone.utc) - timedelta(**{unit: int(rel.group(1))})
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def searchable(rec: Dict[str, Any], where: str) -> str:
    parts = []
    if where in ("answer", "all"):
        parts.append(rec.get("answer") or "")
        parts += list((rec.get("system_answers") or {}).values())
    if where in ("query", "all"):
        parts.append(rec.get("query") or "")
    if where in ("context", "all"):
        parts += [c.get("preview", "") for c in rec.get("retrieved_context", [])]
    return "\n".join(parts)


def snippet(text: str, pattern: Optional[re.Pattern], width: int = 70) -> str:
    text = text.replace("\n", " ")
    m = pattern.search(text) if pattern else None
    if not m:
        return text[:width]
    start = max(0, m.start() - width // 2)
    return ("…" if start else "") + text[start:start + width]


def matches(rec: Dict[str, Any], a: argparse.Namespace, pattern: Optional[re.Pattern]) -> bool:
    ts = datetime.fromisoformat(rec["timestamp"])
    if a.since and ts < a.since:
        return False
    if a.until and ts > a.until:
        return False
    for field in ("user_id", "session_id", "prompt_version", "input_type", "mode", "status"):
        wanted = getattr(a, field)
        if wanted and str(rec.get(field)) != wanted:
            return False
    if a.code_only and not rec.get("answer_has_code"):
        return False
    if a.context and not any(a.context in cid for cid in rec.get("context_ids", [])):
        return False
    if pattern and not pattern.search(searchable(rec, a.where)):
        return False
    return True


def cost(rec: Dict[str, Any]) -> float:
    return rec.get("totals", {}).get("cost_usd", 0.0) or 0.0


def print_table(rows: List[Dict[str, Any]], pattern: Optional[re.Pattern], where: str) -> None:
    print(f"{'timestamp (UTC)':<20} {'trace_id':<12} {'user':<12} {'mode':<8} {'input_type':<15} {'prompt':<10} "
          f"{'cost $':>10} {'ms':>7}  match")
    for r in rows:
        text = searchable(r, "answer" if where == "all" and pattern and pattern.search(r.get("answer") or "") else where)
        print(f"{r['timestamp'][:19]:<20} {r['trace_id'][:12]:<12} {str(r.get('user_id'))[:12]:<12} "
              f"{str(r.get('mode')):<8} {str(r.get('input_type')):<15} {str(r.get('prompt_version')):<10} "
              f"{cost(r):>10.6f} {r.get('totals', {}).get('latency_ms', 0):>7.0f}  {snippet(text, pattern)}")
    print(f"\n{len(rows)} matching request(s)")


def print_stats(records: List[Dict[str, Any]]) -> None:
    costs = sorted(cost(r) for r in records)
    lat = sorted(r.get("totals", {}).get("latency_ms", 0) for r in records)
    pct = lambda xs, p: xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0
    print(f"requests: {len(records)}")
    print(f"cost/query  p50 ${pct(costs, .5):.6f}  p95 ${pct(costs, .95):.6f}  mean ${statistics.mean(costs) if costs else 0:.6f}")
    print(f"latency ms  p50 {pct(lat, .5):.0f}  p95 {pct(lat, .95):.0f}")
    stage = {s: sum(r.get("cost_by_stage", {}).get(s, 0) for r in records) / max(1, len(records))
             for s in ("retrieval", "generation", "tool")}
    print("mean cost by stage: " + "  ".join(f"{k} ${v:.6f}" for k, v in stage.items()))
    for field in ("prompt_version", "input_type", "mode", "user_id", "status"):
        counts: Dict[str, int] = {}
        for r in records:
            counts[str(r.get(field))] = counts.get(str(r.get(field)), 0) + 1
        print(f"{field}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p.add_argument("--text", help="regex, case-insensitive")
    p.add_argument("--in", dest="where", choices=["all", "answer", "query", "context"], default="all")
    p.add_argument("--since", type=parse_time)
    p.add_argument("--until", type=parse_time)
    p.add_argument("--user", dest="user_id")
    p.add_argument("--session", dest="session_id")
    p.add_argument("--prompt-version")
    p.add_argument("--input-type")
    p.add_argument("--mode")
    p.add_argument("--status", choices=["ok", "error"])
    p.add_argument("--context", help="only requests that retrieved this context id (or doc id / filename prefix)")
    p.add_argument("--code-only", action="store_true", help="only answers containing a code block")
    p.add_argument("--cost-outliers", action="store_true", help="only requests above the p95 cost/query")
    p.add_argument("--stats", action="store_true")
    p.add_argument("--show", metavar="TRACE_ID", help="print one full record (a unique id prefix is enough)")
    p.add_argument("--out", type=Path, help="with --show: also write the record to this file")
    p.add_argument("--limit", type=int, default=50)
    a = p.parse_args()
    # Answers contain characters the Windows console code page cannot print
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not a.log.exists():
        print(f"No trace log at {a.log}", file=sys.stderr)
        return 1
    records = list(load(a.log))

    if a.show:
        found = [r for r in records if r["trace_id"].startswith(a.show)]
        if len(found) != 1:
            print(f"{len(found)} traces match '{a.show}'", file=sys.stderr)
            return 1
        text = json.dumps(found[0], indent=2, ensure_ascii=False)
        print(text)
        if a.out:
            a.out.write_text(text + "\n", encoding="utf-8")
            print(f"\nwritten to {a.out}", file=sys.stderr)
        return 0

    if a.stats:
        print_stats(records)
        return 0

    pattern = re.compile(a.text, re.IGNORECASE) if a.text else None
    rows = [r for r in records if matches(r, a, pattern)]
    if a.cost_outliers and records:
        costs = sorted(cost(r) for r in records)
        p95 = costs[min(len(costs) - 1, int(0.95 * len(costs)))]
        rows = sorted((r for r in rows if cost(r) >= p95), key=cost, reverse=True)
    else:
        rows.sort(key=lambda r: r["timestamp"], reverse=True)
    print_table(rows[:a.limit], pattern, a.where)
    return 0


if __name__ == "__main__":
    sys.exit(main())
