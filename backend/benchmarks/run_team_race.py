"""
Week 10: race the single agent against the docs squad (manager + 2 specialists) on the same tests.

    python benchmarks/seed_week10_docs.py                 # once: index the race document
    python benchmarks/run_team_race.py --repeats 3        # run (resumes from results/week10/runs.jsonl)
    python benchmarks/run_team_race.py --summarize-only   # rebuild race.csv / summary.json / summary.md

Groq's free tier allows 200K tokens and 1,000 requests per model per day, and one question pair costs about
10-12K tokens, so a large race spans several days on the free tier. When a limit is hit the race waits (up to
--max-wait-minutes) or stops; run the same command again to resume.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")  # answers contain characters the Windows console code page cannot print

from app.services.llm import client  # noqa: E402
from app.services.llm.client import cooldown_remaining, set_models  # noqa: E402
from app.evaluation import team_race  # noqa: E402
from app.evaluation.judge import JUDGE_MODEL, JUDGE_VERSION  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 10 single-vs-team race")
    parser.add_argument("--systems", default="single,team", help="comma-separated: single, team, team_full")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--ids", default="", help="comma-separated question ids to run (default: all)")
    parser.add_argument("--limit", type=int, default=0, help="run only the first N questions")
    parser.add_argument("--pause", type=float, default=30.0, help="seconds between runs (free tier: 8K tokens/min)")
    parser.add_argument("--max-wait-minutes", type=float, default=15.0, help="wait this long for a rate limit, else stop")
    parser.add_argument("--retries", type=int, default=2,
                        help="retry a run that fails for a reason other than rate limits; then it counts as a wrong answer")
    parser.add_argument("--model", default=team_race.CONTESTANT_MODEL)
    parser.add_argument("--doc-id", default=team_race.DOC_ID)
    parser.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--rejudge", action="store_true",
                        help="judge again the runs whose judging failed or was done by an older judge version")
    args = parser.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    unknown = [s for s in systems if s not in team_race.SYSTEMS]
    if unknown:
        sys.exit(f"Unknown systems {unknown}; choose from {list(team_race.SYSTEMS)}")
    questions = team_race.load_questions()
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    if args.limit:
        questions = questions[:args.limit]

    if not args.summarize_only:
        set_models([args.model])  # every contestant call (and the retriever's query expansion) uses this model
        # One run can exceed the free tier's 8K tokens/minute: let each call wait out the per-minute window
        # (waits are excluded from latency) instead of failing and restarting the whole run
        client.MAX_COOLDOWN_WAIT_SECONDS = 65
        client.RATE_LIMIT_RETRIES = 5
        team_race.CONTESTANT_MODEL = args.model
        check_setup(args.doc_id)
        if args.rejudge:
            rejudge(questions)
        race(questions, systems, args)

    rows = team_race.load_runs()
    summary = team_race.summarize(rows, questions, systems)
    team_race.write_outputs(rows, summary)
    print("\n" + team_race.summary_markdown(summary))
    print(f"Written to {team_race.RACE_DIR}: runs.jsonl, race.csv, summary.json, summary.md")


def check_setup(doc_id: str) -> None:
    from app.services import vector_store_service
    from app.mcp.client.manager import mcp_client_manager
    if doc_id not in vector_store_service.documents_store:
        sys.exit(f"Document '{doc_id}' is not indexed. Run: python benchmarks/seed_week10_docs.py")
    # With an external MCP server enabled the single agent spends an LLM call per question choosing whether to use
    # it, which the team does not. Switch them off for this process only; the saved configuration is untouched.
    for srv in mcp_client_manager.active_servers():
        srv["is_active"] = False
        print(f"Note: external MCP server '{srv['name']}' is off for this race (not saved).")


def judge_with_retries(row, q, max_wait_minutes: float, attempts: int = 3) -> None:
    """Judge a run; on a judge timeout or rate limit, wait for the judge model and try again."""
    for attempt in range(attempts):
        team_race.judge_row(row, q)
        if not row.get("judge_error"):
            return
        wait = cooldown_remaining([JUDGE_MODEL]) or 0
        if attempt == attempts - 1 or wait > max_wait_minutes * 60:
            print(f"  judging failed ({row['judge_error'][:120]}); fix later with --rejudge")
            return
        time.sleep(wait + 1)


def rejudge(questions) -> None:
    by_id = {q["id"]: q for q in questions}
    for row in team_race.load_runs():
        stale = row.get("quality") is None or row.get("judge_version") != JUDGE_VERSION
        if not row.get("error") and stale and row["question_id"] in by_id:
            judge_with_retries(row, by_id[row["question_id"]], max_wait_minutes=5)
            team_race.append_run(row)
            print(f"re-judged {row['system']} {row['question_id']} r{row['repeat']}: quality={row.get('quality')}")


def race(questions, systems, args) -> None:
    done = {(r["system"], r["question_id"], r["repeat"]) for r in team_race.load_runs() if not r.get("error")}
    agents = {s: team_race.SYSTEMS[s]() for s in systems}
    plan = team_race.schedule(questions, systems, args.repeats)
    todo = sum(1 for rep, q, order in plan for s in order if (s, q["id"], rep) not in done)
    print(f"Race: {len(questions)} questions x {args.repeats} repeats x {systems} on {args.doc_id} with {args.model}; "
          f"judge {JUDGE_MODEL}. {todo} runs to go.")

    failures = team_race.failure_counts()
    finished = 0
    for repeat, q, order in plan:
        for system in order:
            key = (system, q["id"], repeat)
            if key in done:
                continue
            while True:
                row = team_race.run_one(system, agents[system], q, repeat, args.doc_id)
                if not row["error"]:
                    row["failed_attempts"] = failures.get(key, 0)
                    break
                team_race.append_run(row)
                if not row["rate_limited"]:
                    # The system's own request failed (e.g. the model called a tool that does not exist)
                    failures[key] = failures.get(key, 0) + 1
                    if failures[key] > args.retries:
                        row = team_race.failed_answer(row, failures[key])
                        break
                    print(f"  {system} {q['id']} failed ({row['error'][:110]}); retrying from scratch")
                    continue
                wait = cooldown_remaining()
                if wait is None or wait > args.max_wait_minutes * 60:
                    print(f"\nStopped on {system} {q['id']} r{repeat}: {row['error']}\n"
                          "Run the same command later to resume.")
                    return
                print(f"  rate-limited; waiting {wait:.0f}s and retrying {system} {q['id']}")
                time.sleep(wait + 1)
            if not row.get("failed_answer"):
                judge_with_retries(row, q, args.max_wait_minutes)
            team_race.append_run(row)
            finished += 1
            print(f"[{finished}/{todo}] r{repeat} {q['id']:<4} {system:<9} quality={row.get('quality')} "
                  f"tokens={row['total_tokens']:>6} calls={row['llm_calls']:>2} cost=${row['cost_usd']:.5f} "
                  f"active={row['active_latency_ms'] / 1000:.1f}s wait={row['wait_ms'] / 1000:.0f}s"
                  + (f" failed_attempts={row['failed_attempts']}" if row.get("failed_attempts") else "")
                  + (" FAILED ANSWER" if row.get("failed_answer") else "")
                  + (" FELL BACK" if row["fell_back"] else ""))
            time.sleep(args.pause)


if __name__ == "__main__":
    main()
