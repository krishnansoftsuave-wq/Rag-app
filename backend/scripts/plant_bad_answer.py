"""
For the squadmate running the support drill: hide one bad answer in logs/requests.jsonl.

Takes a real trace (e.g. a request answered with the deprecated put_object) and re-inserts it at a random time in
the last N days, with a new trace id, user and session, so the person doing the drill cannot spot it by position or
id. Like the seeded background traffic it is marked "synthetic": true (its timestamp and user are made up), so that
field gives nothing away. Prints what was planted; keep that to yourself until the drill is over.

  python scripts/plant_bad_answer.py --from-trace bad_trace.json --days 7
"""
import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "requests.jsonl"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from-trace", type=Path, required=True, help="a full trace record (JSON), e.g. from find_trace.py --show --out")
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--user", default=None, help="user id to plant it under (default: random u_NNN)")
    a = p.parse_args()

    rng = random.SystemRandom()
    record = json.loads(a.from_trace.read_text(encoding="utf-8"))
    ts = datetime.now(timezone.utc) - timedelta(seconds=rng.uniform(3600, a.days * 86400))
    record.update({
        "trace_id": uuid.uuid4().hex,
        "timestamp": ts.isoformat(timespec="milliseconds"),
        "user_id": a.user or f"u_{rng.randint(1, 40):03d}",
        "username": None,
        "session_id": f"chat_{rng.getrandbits(32):08x}",
        "synthetic": True,
    })

    records = [json.loads(line) for line in a.log.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = sorted(records + [record], key=lambda r: r["timestamp"])
    with open(a.log, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Planted trace {record['trace_id']} at {record['timestamp']} for user {record['user_id']} "
          f"({len(records)} records in {a.log})")


if __name__ == "__main__":
    main()
