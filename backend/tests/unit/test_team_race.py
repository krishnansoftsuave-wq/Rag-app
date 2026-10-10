"""Week 10: agent team, A2A hand-offs, usage metering and the race summary. No network calls."""
import contextvars
import math
import os
import sys
import threading
from contextlib import contextmanager
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # backend/

from app.agents.budgets import AgentBudgets
from app.agents.team import manager as manager_module
from app.agents.team import specialists as specialists_module
from app.agents.team.a2a import AgentCard, AgentSkill, Message, TaskState, send_message
from app.agents.team.manager import Manager, SubTask, parse_plan
from app.agents.team.specialists import parse_findings
from app.agents.team.team_agent import TeamRAGAgent
from app.evaluation import judge as judge_module
from app.evaluation import team_race
from app.services.llm import client
from app.services.llm.pricing import call_cost


@contextmanager
def patched(obj, name, value):
    """Temporarily replace obj.name (a dependency-free stand-in for pytest's monkeypatch)."""
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


def _groq_response(prompt_tokens, completion_tokens, cached=0):
    return SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached)))


def _card(name):
    return AgentCard(name=name, description=f"{name} agent", skills=[AgentSkill(id=name, name=name, description=name)])


# --- planning and findings ---------------------------------------------------

def test_parse_plan_merges_per_specialist_and_drops_unknown():
    text = ('{"sub_tasks": [{"to": "concepts", "ask": "How does X work?"}, {"to": "reference", "ask": "Default of X?"},'
            ' {"to": "Concepts", "ask": "Why X?"}, {"to": "lawyer", "ask": "?"}, {"to": "reference", "ask": ""}]}')
    plan = parse_plan(text, ["concepts", "reference"])
    assert [(st.to, st.ask) for st in plan] == [("concepts", "How does X work? Also: Why X?"), ("reference", "Default of X?")]


def test_plan_falls_back_to_every_specialist_on_unusable_reply():
    with patched(manager_module, "complete", lambda *a, **k: ("no json here", "m")):
        plan, fallback = Manager().plan("Q?", [_card("concepts"), _card("reference")])
    assert fallback and [(st.to, st.ask) for st in plan] == [("concepts", "Q?"), ("reference", "Q?")]


def test_parse_findings_json_and_free_text():
    parsed = parse_findings('Sure: {"findings": [{"fact": "Timeout is 30 seconds.", "source": "doc#3"}, {"x": 1}], "not_found": ["retention"]}')
    assert parsed == {"findings": [{"fact": "Timeout is 30 seconds.", "source": "doc#3"}], "not_found": ["retention"]}
    assert parse_findings("plain answer") == {"findings": [{"fact": "plain answer", "source": ""}], "not_found": []}


# --- A2A lifecycle -------------------------------------------------------------

class _EchoAgent:
    card = _card("echo")

    def handle(self, task):
        task.add_artifact("findings", {"findings": [{"fact": task.history[-1].text}], "not_found": []})


class _BrokenAgent:
    card = _card("broken")

    def handle(self, task):
        raise RuntimeError("search index offline")


def test_send_message_completes_task_with_artifacts():
    task = send_message(_EchoAgent(), Message.build("user", "find X", {"document_id": "d1"}), context_id="q1")
    assert task.state == TaskState.COMPLETED
    assert [t["state"] for t in task.transitions] == ["submitted", "working", "completed"]
    assert task.artifact("findings")["findings"][0]["fact"] == "find X"
    assert task.history[0].data == {"document_id": "d1"}
    assert task.to_dict()["status"]["state"] == "completed"


def test_send_message_marks_failed_instead_of_raising():
    task = send_message(_BrokenAgent(), Message.build("user", "find X"), context_id="q1")
    assert task.state == TaskState.FAILED and "search index offline" in task.status_message


def test_agent_card_uses_a2a_field_names():
    card = _card("concepts").to_dict()
    assert {"protocolVersion", "name", "description", "url", "version", "capabilities", "defaultInputModes",
            "defaultOutputModes", "skills"} <= set(card)


# --- usage metering and pricing --------------------------------------------------

def test_call_cost_uses_cached_rate_and_flags_unknown_models():
    assert math.isclose(call_cost("openai/gpt-oss-120b", 1_000_000, 0, 1_000_000), 0.75)
    assert math.isclose(call_cost("openai/gpt-oss-120b", 1_000_000, 1_000_000, 0), 0.075)
    assert call_cost("some/unknown-model", 10, 0, 10) is None


def test_retry_hint_reads_milliseconds_as_milliseconds():
    assert math.isclose(client.retry_hint_seconds("Please try again in 105ms. Need more tokens?"), 0.105)
    assert math.isclose(client.retry_hint_seconds("Please try again in 7m15.3s."), 435.3)
    assert math.isclose(client.retry_hint_seconds("try again in 1h2m"), 3720)
    assert math.isclose(client.retry_hint_seconds("Please try again in 9s."), 9)
    assert client.retry_hint_seconds("model overloaded") is None


def test_meters_nest_and_follow_labels_into_threads():
    with patched(client, "PROVIDER", "groq"), client.track_usage() as outer:
        with client.usage_label("manager.plan"):
            client._metered("openai/gpt-oss-120b", _groq_response(100, 10))
        with client.track_usage() as inner:
            def worker(label):
                with client.usage_label(label):
                    client._metered("openai/gpt-oss-120b", _groq_response(200, 20, cached=50))
            threads = [threading.Thread(target=contextvars.copy_context().run, args=(worker, name))
                       for name in ("concepts", "reference")]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
    assert outer.input_tokens == 500 and outer.output_tokens == 50 and outer.cached_input_tokens == 100
    assert inner.input_tokens == 400 and len(inner.calls) == 2
    assert set(outer.by_label()) == {"manager.plan", "concepts", "reference"}
    assert math.isclose(outer.cost, sum(call_cost("openai/gpt-oss-120b", c.input_tokens, c.cached_input_tokens, c.output_tokens) for c in outer.calls))
    with patched(client, "PROVIDER", "groq"):
        client._metered("openai/gpt-oss-120b", _groq_response(1, 1))  # no active meter: nothing recorded, no error
    assert len(outer.calls) == 3


# --- the team with fake members ----------------------------------------------------

class _FakeSpecialist:
    def __init__(self, name, fail=False):
        self.card = _card(name)
        self.fail = fail

    @property
    def name(self):
        return self.card.name

    def handle(self, task):
        if self.fail:
            raise RuntimeError("rate limited")
        task.add_artifact("findings", {"findings": [{"fact": f"{self.name} fact", "source": "doc#1"}], "not_found": [], "searches": 1})
        task.add_artifact("evidence", {"chunks": [{"doc_id": "d", "chunk_index": self.name, "full_content": "x"}]})
        task.add_artifact("transcript", {"messages": [{"role": "tool", "content": "long search results"}]})


class _FakeManager(Manager):
    def __init__(self):
        self.reports = []

    def plan(self, question, cards):
        return [SubTask(c.name, f"{c.name} part of {question}") for c in cards], False

    def synthesize(self, question, report):
        self.reports.append(report)
        return "final answer"


def test_team_runs_plan_parallel_tasks_and_synthesis():
    mgr = _FakeManager()
    team = TeamRAGAgent(specialists=[_FakeSpecialist("concepts"), _FakeSpecialist("reference")], manager=mgr,
                        budgets=AgentBudgets(max_wall_clock_seconds=30))
    state = team.run("How and how much?", document_id="d")
    assert state.final_answer == "final answer" and state.termination_reason == "completed"
    assert [t.action for t in state.trace] == ["manager_plan", "a2a_task:concepts", "a2a_task:reference", "manager_synthesize"]
    assert len(state.retrieved_evidence) == 2
    assert "Findings from concepts" in mgr.reports[0] and "long search results" not in mgr.reports[0]


def test_specialist_llm_outage_fails_the_run_instead_of_a_partial_answer():
    class _RateLimited(_FakeSpecialist):
        def handle(self, task):
            raise client.LLMUnavailableError("rate limit reached (429)")

    team = TeamRAGAgent(specialists=[_FakeSpecialist("concepts"), _RateLimited("reference")], manager=_FakeManager())
    try:
        team.run("Q?", document_id="d")
        raise AssertionError("an LLM outage inside a specialist must fail the run")
    except client.LLMUnavailableError as err:
        assert "429" in str(err)


def test_full_handoff_sends_transcripts_and_failed_task_is_reported():
    mgr = _FakeManager()
    team = TeamRAGAgent(handoff="full", specialists=[_FakeSpecialist("concepts"), _FakeSpecialist("reference", fail=True)], manager=mgr)
    state = team.run("Q?", document_id="d")
    assert state.termination_reason == "completed_partial"
    assert "long search results" in mgr.reports[0]
    assert "reference could not complete" in mgr.reports[0]


# --- specialist recovery and the tool-free final turn ---------------------------------

def test_final_turn_is_plain_chat_without_tool_structure():
    history = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "Sub-task: x"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "search", "arguments": '{"query": "x"}'}}]},
        {"role": "tool", "tool_call_id": "1", "content": '{"results": []}'},
    ]
    plain = client._as_plain_chat(history)
    assert all("tool_calls" not in m and m["role"] != "tool" for m in plain)
    assert plain[2]["content"] == 'Called: search({"query": "x"})' and plain[3]["content"].startswith("Tool result:")


class _ScriptedChat:
    """Stands in for ToolChat: each tool-enabled step follows the script ("call" or "fail")."""
    script: list = []

    def __init__(self, system, user, tools):
        self.allowed, self.notes, self.history = [], [], []

    def step(self, allow_tools=True):
        self.allowed.append(allow_tools)
        _ScriptedChat.last = self
        if not allow_tools:
            return [], '{"findings": [{"fact": "Timeout is 30 seconds.", "source": "doc#3"}], "not_found": []}'
        if _ScriptedChat.script.pop(0) == "fail":
            raise client.LLMUnavailableError("400 tool_use_failed: model called a tool that does not exist")
        return [client.ToolCall("c1", "fake_search", {"query": "timeout"})], ""

    def add_note(self, text):
        self.notes.append(text)

    def add_tool_result(self, call, result):
        pass


def fake_search(query: str, document_id: str = None):
    return {"results": [{"doc_id": "d", "chunk_index": len(query), "full_content": "The default timeout is 30 seconds."}]}


def _run_specialist(script):
    _ScriptedChat.script = list(script)
    with patched(specialists_module, "ToolChat", _ScriptedChat):
        spec = specialists_module.Specialist(_card("reference"), "instructions", fake_search, max_steps=3)
        task = send_message(spec, Message.build("user", "Find the default timeout", {"document_id": "d"}), "q")
    return task, _ScriptedChat.last


def test_specialist_recovers_from_broken_tool_calls_by_searching_itself():
    task, chat = _run_specialist(["fail"])
    assert task.state == TaskState.COMPLETED
    assert chat.allowed == [True, False]  # failed tool turn, then the tool-free report
    assert task.artifact("findings")["searches"] == 1 and any("Search results for the sub-task" in n for n in chat.notes)
    assert task.artifact("findings")["findings"][0]["fact"] == "Timeout is 30 seconds."


def test_specialist_reports_without_tools_once_its_searches_are_used_up():
    task, chat = _run_specialist(["call", "call", "call"])
    assert chat.allowed == [True, True, True, False]
    assert task.artifact("findings")["searches"] == 3 and len(task.artifact("evidence")["chunks"]) == 1


# --- judge ------------------------------------------------------------------------

def test_judge_scores_and_rejects_unreadable_replies():
    reply = '<think>hmm</think>{"correctness": 5, "completeness": 3, "groundedness": 5, "missing": ["retention"], "errors": [], "rationale": "ok"}'
    with patched(judge_module, "complete", lambda *a, **k: (reply, "m")):
        v = judge_module.judge_answer("Q", "ref", "answer", ["a", "b"])
    assert math.isclose(v["quality"], 13 / 3, abs_tol=0.001) and v["passed"] is False and v["missing"] == ["retention"]

    with patched(judge_module, "complete", lambda *a, **k: ("not json", "m")):
        try:
            judge_module.judge_answer("Q", "ref", "answer")
            raise AssertionError("an unreadable judge reply must raise")
        except ValueError:
            pass
    assert judge_module.judge_answer("Q", "ref", "  ")["passed"] is False


# --- race summary and decision rule --------------------------------------------------

def _row(system, qid, repeat, quality, cost, tokens, latency, category="single_fact"):
    return {"system": system, "question_id": qid, "category": category, "repeat": repeat, "error": None,
            "quality": quality, "correctness": quality, "completeness": quality, "groundedness": quality,
            "passed": quality >= 4, "keyword_passed": True, "latency_ms": latency, "active_latency_ms": latency,
            "input_tokens": tokens, "output_tokens": 0, "total_tokens": tokens, "llm_calls": 3, "cost_usd": cost,
            "fell_back": False, "termination_reason": "completed", "by_role": {}, "handoff_tokens_approx": None,
            "judge_version": judge_module.JUDGE_VERSION}


def test_complete_pairs_keeps_only_questions_every_system_finished():
    rows = [_row("single", "W1", 1, 4, 0.001, 100, 1000), _row("team", "W1", 1, 4, 0.002, 200, 2000),
            _row("single", "W2", 1, 4, 0.001, 100, 1000), {**_row("team", "W2", 1, 4, 0.002, 200, 2000), "error": "429"},
            _row("single", "W3", 1, 4, 0.001, 100, 1000), {**_row("team", "W3", 1, 4, 0.002, 200, 2000), "judge_version": 1}]
    assert {(r["system"], r["question_id"]) for r in team_race.complete_pairs(rows, ["single", "team"])} == {("single", "W1"), ("team", "W1")}


def test_failures_other_than_rate_limits_become_wrong_answers():
    assert team_race.is_rate_limit("Groq is unavailable (last error: m: rate limit reached (429)). Try again in about 2 min.")
    assert not team_race.is_rate_limit("Groq is unavailable (last error: m: BadRequestError: Model called python tool which was not enabled)")
    row = team_race.failed_answer({**_row("single", "W4", 1, 5, 0.001, 100, 1000), "error": "BadRequestError: 400"}, attempts=3)
    assert row["error"] is None and row["failure"] == "BadRequestError: 400" and row["failed_attempts"] == 3
    assert row["quality"] == 1.0 and row["passed"] is False
    pair = [row, _row("team", "W4", 1, 5, 0.001, 100, 1000)]
    assert len(team_race.complete_pairs(pair, ["single", "team"])) == 2  # the failure counts, it is not dropped


def test_decide_keeps_team_only_when_quality_cost_and_latency_all_pass():
    single = {"quality": 3.5, "cost_per_question": 0.001, "latency_p50_ms": 4000, "quality_noise": 0.1}
    good_team = {"quality": 4.2, "cost_per_question": 0.0018, "latency_p50_ms": 6000, "quality_noise": 0.1}
    assert team_race.decide(single, good_team)["keep"] == "team"
    assert team_race.decide(single, {**good_team, "cost_per_question": 0.003})["keep"] == "single"
    noisy = team_race.decide({**single, "quality_noise": 0.8}, good_team)
    assert noisy["keep"] == "single" and noisy["checks"]["quality_gain"]["needed"] == ">= 0.8"


def test_summary_and_markdown_render():
    questions = [{"id": "W1", "category": "single_fact"}, {"id": "W2", "category": "multi_part"}]
    rows = []
    for rep in (1, 2):
        rows += [_row("single", "W1", rep, 5, 0.001, 3000, 3000), _row("team", "W1", rep, 5, 0.002, 6000, 7000),
                 _row("single", "W2", rep, 3, 0.001, 3000, 3000, "multi_part"), _row("team", "W2", rep, 4.5, 0.002, 6000, 7000, "multi_part")]
    s = team_race.summarize(rows, questions, ["single", "team"])
    assert s["comparison"]["cost_ratio"] == 2.0 and s["comparison"]["categories_where_team_wins"] == ["multi_part"]
    assert s["comparison"]["per_question_wins"] == {"team": 1, "tie": 1, "single": 0}
    # Quality +0.75 and cost 2.0x pass, but latency 2.33x fails the rule
    assert s["verdict"]["checks"]["quality_gain"]["ok"] and s["verdict"]["checks"]["cost_ratio"]["ok"]
    assert s["verdict"]["keep"] == "single"
    md = team_race.summary_markdown(s)
    assert "## The four numbers" in md and "**Keep: single**" in md


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        fn()
        print(f"   {name} PASSED")
    print(f"All {len(tests)} Week 10 tests passed.")
