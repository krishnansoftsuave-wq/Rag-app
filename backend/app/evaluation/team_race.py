"""
Week 10 race: the single AdaptiveRAGAgent against the docs squad (manager + concepts + reference specialists).

Fairness: both systems answer the same questions over the same document (`w10_novacloud`), with the same
retriever, the same pinned model and the same budgets, back to back per question (alternating which goes
first). Tokens and cost are the provider-reported usage of every LLM call a run makes, including the retriever's
query expansion. Latency is reported without time spent waiting on rate limits. Answers are scored by a blind
judge on another model family, outside the contestants' usage.

Runs are appended to results/week10/runs.jsonl as they finish, so a race stopped by a daily rate limit resumes
where it stopped. Summaries use only complete pairs (every system answered that question in that repeat).
"""
import csv
import json
import os
import random
import re
import statistics
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from app.agents.budgets import AgentBudgets
from app.agents.rag_agent import AdaptiveRAGAgent
from app.agents.team.team_agent import TeamRAGAgent
from app.core.config import BASE_DIR
from app.evaluation.evaluator import evaluate_answer
from app.evaluation.judge import JUDGE_MODEL, JUDGE_VERSION, judge_answer
from app.services.llm.client import LLMUnavailableError, track_usage, usage_label

QUESTIONS_PATH = str(BASE_DIR / "benchmarks" / "questions_week10.json")
DOCS_PATH = str(BASE_DIR / "benchmarks" / "novacloud_docs.txt")
RACE_DIR = str(BASE_DIR / "results" / "week10")
RUNS_PATH = os.path.join(RACE_DIR, "runs.jsonl")
DOC_ID = "w10_novacloud"
CONTESTANT_MODEL = "openai/gpt-oss-120b"

# Decision rule, fixed before the race was run. Keep the team only if all three hold.
MIN_QUALITY_GAIN = 0.3   # judge points on the 1-5 scale; the gain must also exceed the run-to-run noise
MAX_COST_RATIO = 2.0     # team cost per question / single cost per question
MAX_LATENCY_RATIO = 2.0  # team p50 latency / single p50 latency


def race_budgets() -> AgentBudgets:
    """The same, generous budgets for both systems, so a budget cut-off does not decide the race. The wall clock
    is long because it includes time spent waiting on the free tier's tokens-per-minute limit."""
    return AgentBudgets(max_iterations=12, max_tokens=40000, max_cost=0.05, max_wall_clock_seconds=600.0)


SYSTEMS: Dict[str, Callable[[], Any]] = {
    "single": lambda: AdaptiveRAGAgent(budgets=race_budgets()),
    "team": lambda: TeamRAGAgent(budgets=race_budgets()),
    # Ablation: specialists hand back their whole conversation instead of compact findings
    "team_full": lambda: TeamRAGAgent(handoff="full", budgets=race_budgets()),
}


def load_questions(path: str = QUESTIONS_PATH) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_doc_pages(path: str = DOCS_PATH) -> Dict[int, str]:
    """The race document split at its "Page N —" headings, for the judge's groundedness check."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return {int(m.group(1)): m.group(0).strip()
            for m in re.finditer(r"^Page (\d+) —.*?(?=^Page \d+ —|\Z)", text, re.M | re.S)}


# ---------------------------------------------------------------------------
# Running and judging
# ---------------------------------------------------------------------------

def run_one(system: str, agent: Any, q: Dict[str, Any], repeat: int, doc_id: str = DOC_ID) -> Dict[str, Any]:
    """One system answering one question, with its real usage. An LLM outage is recorded as the run's error."""
    error, state = None, None
    with track_usage() as meter, usage_label(system):
        start = time.perf_counter()
        try:
            state = agent.run(question=q["question"], document_id=doc_id, question_id=f"{q['id']}-r{repeat}")
        except LLMUnavailableError as err:
            error = str(err)
        latency_ms = (time.perf_counter() - start) * 1000

    trace = [t.to_dict() for t in state.trace] if state else []
    synth = next((t for t in trace if t["action"] == "manager_synthesize"), None)
    plan = next((t for t in trace if t["action"] == "manager_plan"), None)
    return {
        "system": system,
        "question_id": q["id"],
        "category": q.get("category", ""),
        "repeat": repeat,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "error": error,
        "rate_limited": is_rate_limit(error),
        "answer": state.final_answer if state else "",
        "termination_reason": state.termination_reason if state else "error",
        "latency_ms": round(latency_ms, 1),
        "wait_ms": round(meter.wait_seconds * 1000, 1),
        "active_latency_ms": round(latency_ms - meter.wait_seconds * 1000, 1),
        "llm_calls": len(meter.calls),
        "input_tokens": meter.input_tokens,
        "cached_input_tokens": meter.cached_input_tokens,
        "output_tokens": meter.output_tokens,
        "total_tokens": meter.total_tokens,
        "cost_usd": round(meter.cost, 7),
        "models": meter.models,
        "unpriced_models": meter.unpriced_models,
        "fell_back": any(m != CONTESTANT_MODEL for m in meter.models),
        "by_role": meter.by_label(),
        "plan": plan["details"].get("sub_tasks") if plan else None,
        "handoff_tokens_approx": synth["details"].get("handoff_tokens_approx") if synth else None,
        "trace": trace,
    }


def judge_row(row: Dict[str, Any], q: Dict[str, Any]) -> Dict[str, Any]:
    """Add the blind judge's scores and the keyword-overlap score (kept as a second opinion) to a run."""
    keyword = evaluate_answer(row["answer"], q["expected_answer"], q.get("category", ""))
    row.update({"keyword_score": keyword["score"], "keyword_passed": keyword["passed"]})
    pages = load_doc_pages()
    evidence = "\n\n".join(pages[n] for n in q.get("evidence_pages", []) if n in pages)
    try:
        verdict = judge_answer(q["question"], q["expected_answer"], row["answer"], q.get("asks"), evidence=evidence)
        row.update({**verdict, "judge_model": JUDGE_MODEL, "judge_version": JUDGE_VERSION, "judge_error": None})
    except (LLMUnavailableError, ValueError) as err:
        row.update({"quality": None, "passed": None, "judge_error": str(err)})
    return row


def is_rate_limit(error: Optional[str]) -> bool:
    """A rate limit or provider outage (wait and resume), as opposed to the system's own request failing."""
    text = (error or "").lower()
    return bool(error) and any(m in text for m in ("(429)", "rate limit", "(503)", "overloaded", "timed out"))


def failed_answer(row: Dict[str, Any], attempts: int) -> Dict[str, Any]:
    """A run that failed on every attempt for a reason other than rate limits counts as a wrong answer."""
    return {**row, "failure": row["error"], "error": None, "failed_answer": True, "failed_attempts": attempts,
            "quality": 1.0, "correctness": 1, "completeness": 1, "groundedness": 1, "passed": False,
            "keyword_score": 0.0, "keyword_passed": False, "judge_version": JUDGE_VERSION, "judge_error": None,
            "rationale": f"The system failed to answer: {row['error'][:200]}"}


def failure_counts(path: str = RUNS_PATH) -> Dict[Tuple[str, str, int], int]:
    """How many attempts of each run failed for a reason other than rate limits."""
    counts: Dict[Tuple[str, str, int], int] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line) if line.strip() else {}
                if row.get("error") and not is_rate_limit(row["error"]):
                    key = (row["system"], row["question_id"], row["repeat"])
                    counts[key] = counts.get(key, 0) + 1
    return counts


def load_runs(path: str = RUNS_PATH) -> List[Dict[str, Any]]:
    """The latest row per (system, question, repeat)."""
    if not os.path.exists(path):
        return []
    latest: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                latest[(row["system"], row["question_id"], row["repeat"])] = row
    return list(latest.values())


def append_run(row: Dict[str, Any], path: str = RUNS_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def schedule(questions: List[Dict[str, Any]], systems: List[str], repeats: int, seed: int = 10) -> List[Tuple[int, Dict[str, Any], List[str]]]:
    """(repeat, question, system order) in run order: repeat by repeat, both systems back to back per question,
    with a seeded shuffle of which system goes first so neither always runs on a fresh rate-limit window."""
    rng = random.Random(seed)
    plan = []
    for repeat in range(1, repeats + 1):
        for q in questions:
            order = list(systems)
            rng.shuffle(order)
            plan.append((repeat, q, order))
    return plan


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _mean(values: List[float], digits: int = 4) -> Optional[float]:
    values = [v for v in values if v is not None]
    return round(float(np.mean(values)), digits) if values else None


def _pct(values: List[float], q: float) -> Optional[float]:
    return round(float(np.percentile(values, q)), 1) if values else None


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return round(a / b, 3) if a is not None and b else None


def complete_pairs(rows: List[Dict[str, Any]], systems: List[str]) -> List[Dict[str, Any]]:
    """Rows of (question, repeat) pairs that every system finished without an error and the current judge scored."""
    ok = [r for r in rows if not r.get("error") and r.get("quality") is not None
          and r.get("judge_version") == JUDGE_VERSION and r["system"] in systems]
    keys: Dict[Tuple[str, int], set] = {}
    for r in ok:
        keys.setdefault((r["question_id"], r["repeat"]), set()).add(r["system"])
    full = {k for k, s in keys.items() if s >= set(systems)}
    return [r for r in ok if (r["question_id"], r["repeat"]) in full]


BUDGET_STOPS = ("max_iterations", "max_tokens", "max_cost", "wall_clock")  # AgentBudgets termination reasons


def system_stats(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    active = [r["active_latency_ms"] for r in runs]
    by_repeat: Dict[int, List[float]] = {}
    for r in runs:
        by_repeat.setdefault(r["repeat"], []).append(r["quality"])
    repeat_means = [float(np.mean(v)) for _, v in sorted(by_repeat.items())]
    return {
        "runs": len(runs),
        "quality": _mean([r["quality"] for r in runs]),
        "correctness": _mean([r["correctness"] for r in runs]),
        "completeness": _mean([r["completeness"] for r in runs]),
        "groundedness": _mean([r["groundedness"] for r in runs]),
        "pass_rate": round(100 * sum(bool(r["passed"]) for r in runs) / len(runs), 1) if runs else None,
        "keyword_pass_rate": round(100 * sum(bool(r["keyword_passed"]) for r in runs) / len(runs), 1) if runs else None,
        "latency_p50_ms": _pct(active, 50),
        "latency_p95_ms": _pct(active, 95),
        "latency_p50_with_waits_ms": _pct([r["latency_ms"] for r in runs], 50),
        "input_tokens": _mean([r["input_tokens"] for r in runs]),
        "output_tokens": _mean([r["output_tokens"] for r in runs]),
        "total_tokens": _mean([r["total_tokens"] for r in runs]),
        "llm_calls": _mean([r["llm_calls"] for r in runs]),
        "cost_per_question": _mean([r["cost_usd"] for r in runs], digits=7),
        "cost_per_1k_questions": round(1000 * float(np.mean([r["cost_usd"] for r in runs])), 4) if runs else None,
        "quality_by_repeat": [round(m, 3) for m in repeat_means],
        "quality_noise": round(statistics.pstdev(repeat_means), 3) if len(repeat_means) > 1 else None,
        "fell_back_runs": sum(bool(r["fell_back"]) for r in runs),
        "failed_attempts": sum(r.get("failed_attempts", 0) for r in runs),
        "failed_answers": sum(bool(r.get("failed_answer")) for r in runs),
        "budget_stops": sum(r["termination_reason"] in BUDGET_STOPS for r in runs),
    }


ROLE_ORDER = ["manager.plan", "concepts", "reference", "manager.synthesize"]


def role_breakdown(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Mean calls, tokens and cost per question for each role of a team (manager.plan, concepts, ...)."""
    totals: Dict[str, Dict[str, float]] = {}
    for r in runs:
        for role, u in (r.get("by_role") or {}).items():
            t = totals.setdefault(role, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
            for k in t:
                t[k] += u.get(k, 0)
    n = max(1, len(runs))
    order = {role: i for i, role in enumerate(ROLE_ORDER)}
    return {role: {k: round(v / n, 7 if k == "cost" else 1) for k, v in totals[role].items()}
            for role in sorted(totals, key=lambda r: order.get(r, len(order)))}


def decide(single: Dict[str, Any], team: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the pre-registered rule."""
    noise = max(single.get("quality_noise") or 0.0, team.get("quality_noise") or 0.0)
    threshold = max(MIN_QUALITY_GAIN, noise)
    gain = round((team["quality"] or 0) - (single["quality"] or 0), 3)
    cost_ratio = _ratio(team["cost_per_question"], single["cost_per_question"])
    latency_ratio = _ratio(team["latency_p50_ms"], single["latency_p50_ms"])
    checks = {
        "quality_gain": {"value": gain, "needed": f">= {threshold}", "ok": gain >= threshold},
        "cost_ratio": {"value": cost_ratio, "needed": f"<= {MAX_COST_RATIO}", "ok": cost_ratio is not None and cost_ratio <= MAX_COST_RATIO},
        "latency_ratio": {"value": latency_ratio, "needed": f"<= {MAX_LATENCY_RATIO}", "ok": latency_ratio is not None and latency_ratio <= MAX_LATENCY_RATIO},
    }
    keep = "team" if all(c["ok"] for c in checks.values()) else "single"
    return {
        "keep": keep,
        "rule": (f"Keep the team only if its judge quality beats the single agent by at least max({MIN_QUALITY_GAIN}, "
                 f"run-to-run noise = {noise}) AND it costs at most {MAX_COST_RATIO}x AND its p50 latency is at most "
                 f"{MAX_LATENCY_RATIO}x the single agent's."),
        "checks": checks,
    }


def summarize(rows: List[Dict[str, Any]], questions: List[Dict[str, Any]], systems: List[str]) -> Dict[str, Any]:
    paired = complete_pairs(rows, systems)
    by_system = {s: [r for r in paired if r["system"] == s] for s in systems}
    failed_keys = {(r["question_id"], r["repeat"]) for r in paired if r.get("failed_answer")}
    categories = sorted({q.get("category", "") for q in questions})

    summary: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "setup": {"doc_id": DOC_ID, "contestant_model": CONTESTANT_MODEL, "judge_model": JUDGE_MODEL,
                  "systems": systems, "budgets": race_budgets().to_dict()},
        "coverage": {
            "paired_runs_per_system": len(by_system[systems[0]]) if systems else 0,
            "questions_covered": len({r["question_id"] for r in paired}),
            "repeats_covered": sorted({r["repeat"] for r in paired}),
            "errored_runs": sum(1 for r in rows if r.get("error")),
            "unjudged_runs": sum(1 for r in rows if not r.get("error") and
                                 (r.get("quality") is None or r.get("judge_version") != JUDGE_VERSION)),
        },
        "systems": {s: system_stats(runs) for s, runs in by_system.items() if runs},
        # Sensitivity view: only the (question, repeat) pairs where no system had a failed answer
        "both_answered": {s: system_stats([r for r in runs if (r["question_id"], r["repeat"]) not in failed_keys])
                          for s, runs in by_system.items()
                          if any((r["question_id"], r["repeat"]) not in failed_keys for r in runs)},
        "by_category": {},
        "roles": {s: role_breakdown(runs) for s, runs in by_system.items() if s != "single" and runs},
        "handoff_tokens_approx": {s: _mean([r.get("handoff_tokens_approx") for r in runs])
                                  for s, runs in by_system.items() if s != "single" and runs},
        "per_question": [],
    }
    for cat in categories:
        summary["by_category"][cat] = {
            s: {k: v for k, v in system_stats([r for r in runs if r["category"] == cat]).items()
                if k in ("runs", "quality", "pass_rate", "total_tokens", "llm_calls", "cost_per_question", "latency_p50_ms")}
            for s, runs in by_system.items() if any(r["category"] == cat for r in runs)
        }
    for q in questions:
        entry = {"question_id": q["id"], "category": q.get("category", "")}
        for s, runs in by_system.items():
            entry[s] = _mean([r["quality"] for r in runs if r["question_id"] == q["id"]])
        if any(entry.get(s) is not None for s in systems):
            summary["per_question"].append(entry)

    if "single" in summary["systems"] and "team" in summary["systems"]:
        single, team = summary["systems"]["single"], summary["systems"]["team"]
        wins = {"team": 0, "tie": 0, "single": 0}
        for e in summary["per_question"]:
            if e.get("team") is None or e.get("single") is None:
                continue
            diff = e["team"] - e["single"]
            wins["team" if diff >= 0.5 else "single" if diff <= -0.5 else "tie"] += 1
        summary["comparison"] = {
            "quality_delta": round((team["quality"] or 0) - (single["quality"] or 0), 3),
            "pass_rate_delta_pp": round((team["pass_rate"] or 0) - (single["pass_rate"] or 0), 1),
            "token_ratio": _ratio(team["total_tokens"], single["total_tokens"]),
            "input_token_ratio": _ratio(team["input_tokens"], single["input_tokens"]),
            "llm_call_ratio": _ratio(team["llm_calls"], single["llm_calls"]),
            "cost_ratio": _ratio(team["cost_per_question"], single["cost_per_question"]),
            "latency_p50_ratio": _ratio(team["latency_p50_ms"], single["latency_p50_ms"]),
            "per_question_wins": wins,
            "categories_where_team_wins": [
                cat for cat, d in summary["by_category"].items()
                if "team" in d and "single" in d and d["team"]["quality"] is not None and d["single"]["quality"] is not None
                and d["team"]["quality"] - d["single"]["quality"] >= MIN_QUALITY_GAIN
            ],
        }
        summary["verdict"] = decide(single, team)
    return summary


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "system", "question_id", "category", "repeat", "quality", "correctness", "completeness", "groundedness",
    "passed", "keyword_score", "keyword_passed", "latency_ms", "active_latency_ms", "wait_ms", "llm_calls",
    "input_tokens", "cached_input_tokens", "output_tokens", "total_tokens", "cost_usd", "handoff_tokens_approx",
    "termination_reason", "fell_back", "failed_attempts", "failed_answer", "failure", "error", "judge_error",
]


def write_outputs(rows: List[Dict[str, Any]], summary: Dict[str, Any], out_dir: str = RACE_DIR) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "race.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(rows, key=lambda r: (r["repeat"], r["question_id"], r["system"])):
            writer.writerow({k: r.get(k) for k in CSV_FIELDS})
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_markdown(summary))


def _fmt(v: Any, spec: str = "") -> str:
    if v is None:
        return "–"
    return format(v, spec) if spec else str(v)


def summary_markdown(s: Dict[str, Any]) -> str:
    systems = [k for k in s["setup"]["systems"] if k in s["systems"]]
    st = s["systems"]
    cov = s["coverage"]
    lines = [
        "# Week 10 race: single agent vs docs squad",
        "",
        f"Document `{s['setup']['doc_id']}` · contestant model `{s['setup']['contestant_model']}` · "
        f"judge `{s['setup']['judge_model']}` · {cov['paired_runs_per_system']} paired runs per system "
        f"({cov['questions_covered']} questions × repeats {cov['repeats_covered']}) · errored runs: {cov['errored_runs']}",
        "",
        "## The four numbers",
        "",
        "| Metric | " + " | ".join(systems) + " |",
        "|---|" + "---|" * len(systems),
    ]
    rows = [
        ("Quality, judge mean (1-5)", "quality", ".2f"),
        ("Pass rate (all three scores >= 4), %", "pass_rate", ".1f"),
        ("Correctness / completeness / groundedness", None, None),
        ("Latency p50, s (no rate-limit waits)", "latency_p50_ms", "s"),
        ("Latency p95, s (no rate-limit waits)", "latency_p95_ms", "s"),
        ("Tokens per question, input", "input_tokens", ".0f"),
        ("Tokens per question, output", "output_tokens", ".0f"),
        ("LLM calls per question", "llm_calls", ".1f"),
        ("Cost per question, USD", "cost_per_question", ".6f"),
        ("Cost per 1,000 questions, USD", "cost_per_1k_questions", ".3f"),
        ("Quality by repeat", "quality_by_repeat", ""),
        ("Failed attempts, retried (not rate limits)", "failed_attempts", ""),
        ("Failed answers (every attempt failed)", "failed_answers", ""),
    ]
    for label, key, spec in rows:
        cells = []
        for sys_ in systems:
            x = st[sys_]
            if key is None:
                cells.append(f"{_fmt(x['correctness'], '.2f')} / {_fmt(x['completeness'], '.2f')} / {_fmt(x['groundedness'], '.2f')}")
            elif spec == "s":
                cells.append(_fmt(x[key] / 1000 if x[key] is not None else None, ".1f"))
            else:
                cells.append(_fmt(x[key], spec))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    both = s.get("both_answered", {})
    if both and any(st[x]["failed_answers"] for x in systems):
        lines += ["", f"### Only the questions every system answered ({both[systems[0]]['runs']} runs per system)", "",
                  "| Metric | " + " | ".join(systems) + " |", "|---|" + "---|" * len(systems)]
        for label, key, spec in [("Quality, judge mean (1-5)", "quality", ".2f"), ("Latency p50, s", "latency_p50_ms", "s"),
                                 ("Tokens per question (in + out)", "total_tokens", ".0f"),
                                 ("Cost per question, USD", "cost_per_question", ".6f")]:
            cells = [_fmt(both[x][key] / 1000 if spec == "s" and both[x][key] is not None else both[x][key],
                          ".1f" if spec == "s" else spec) for x in systems]
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

    if "comparison" in s:
        c = s["comparison"]
        lines += [
            "",
            "## Team vs single",
            "",
            f"- Quality: {c['quality_delta']:+.2f} judge points; pass rate {c['pass_rate_delta_pp']:+.1f} pp",
            f"- Tokens: {_fmt(c['token_ratio'])}x (input {_fmt(c['input_token_ratio'])}x); LLM calls {_fmt(c['llm_call_ratio'])}x",
            f"- Cost: {_fmt(c['cost_ratio'])}x; latency p50: {_fmt(c['latency_p50_ratio'])}x",
            f"- Per question (mean quality, ±0.5 = tie): team better {c['per_question_wins']['team']}, "
            f"tie {c['per_question_wins']['tie']}, single better {c['per_question_wins']['single']}",
            f"- Categories where the team gains >= {MIN_QUALITY_GAIN}: {', '.join(c['categories_where_team_wins']) or 'none'}",
        ]

    lines += ["", "## By question type", "",
              "| Category | Runs | " + " | ".join(f"Quality {x}" for x in systems) + " | "
              + " | ".join(f"Tokens {x}" for x in systems) + " | " + " | ".join(f"Cost {x}" for x in systems) + " |",
              "|---|---|" + "---|" * (3 * len(systems))]
    for cat, d in s["by_category"].items():
        lines.append(
            f"| {cat} | {_fmt(d.get(systems[0], {}).get('runs'))} | "
            + " | ".join(_fmt(d.get(x, {}).get("quality"), ".2f") for x in systems) + " | "
            + " | ".join(_fmt(d.get(x, {}).get("total_tokens"), ".0f") for x in systems) + " | "
            + " | ".join(_fmt(d.get(x, {}).get("cost_per_question"), ".6f") for x in systems) + " |"
        )

    for sys_, roles in s["roles"].items():
        total = sum(r["input_tokens"] + r["output_tokens"] for r in roles.values()) or 1
        lines += ["", f"## Where the {sys_} tokens go (mean per question)", "",
                  "| Role | LLM calls | Input tokens | Output tokens | Share of tokens | Cost, USD |", "|---|---|---|---|---|---|"]
        for role, r in roles.items():
            share = 100 * (r["input_tokens"] + r["output_tokens"]) / total
            lines.append(f"| {role} | {r['calls']:.1f} | {r['input_tokens']:.0f} | {r['output_tokens']:.0f} | {share:.0f}% | {r['cost']:.6f} |")
        lines.append(f"\nHand-off payload (sub-tasks sent + reports returned, ≈chars/4): "
                     f"{_fmt(s['handoff_tokens_approx'].get(sys_), '.0f')} tokens per question.")

    lines += ["", "## Per question (mean judge quality over repeats)", "",
              "| Question | Category | " + " | ".join(systems) + " |", "|---|---|" + "---|" * len(systems)]
    for e in s["per_question"]:
        lines.append(f"| {e['question_id']} | {e['category']} | " + " | ".join(_fmt(e.get(x), ".2f") for x in systems) + " |")

    if "verdict" in s:
        v = s["verdict"]
        lines += ["", "## Verdict (pre-registered rule)", "", v["rule"], ""]
        for name, chk in v["checks"].items():
            lines.append(f"- {name}: {_fmt(chk['value'])} (needed {chk['needed']}) → {'pass' if chk['ok'] else 'fail'}")
        lines += ["", f"**Keep: {v['keep']}**"]
    return "\n".join(lines) + "\n"
