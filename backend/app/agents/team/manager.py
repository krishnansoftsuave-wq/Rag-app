"""
The team's manager. It never searches. It reads the specialists' AgentCards, splits the question into at most one
sub-task per specialist (grouping the question's asks by the kind of answer they need), and writes the final
answer from what the specialists hand back.
"""
import json
import re
from dataclasses import dataclass
from typing import List, Tuple

from app.agents.team.a2a import AgentCard, Task, TaskState
from app.services.llm.client import complete

HANDOFF_MODES = ("findings", "full")


@dataclass
class SubTask:
    to: str
    ask: str


def parse_plan(text: str, names: List[str]) -> List[SubTask]:
    """The manager's JSON plan as sub-tasks: unknown specialists and empty asks dropped, and two sub-tasks for
    the same specialist merged into one (each specialist gets at most one hand-off)."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    try:
        items = json.loads(match.group(0)).get("sub_tasks", []) if match else []
    except (json.JSONDecodeError, AttributeError):
        items = []
    asks: dict = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        to, ask = str(item.get("to", "")).strip().lower(), str(item.get("ask", "")).strip()
        if to in names and ask:
            asks[to] = f"{asks[to]} Also: {ask}" if to in asks else ask
    return [SubTask(to, ask) for to, ask in asks.items()]


class Manager:
    def plan(self, question: str, cards: List[AgentCard]) -> Tuple[List[SubTask], bool]:
        """Sub-tasks for the question, and whether the fallback plan (whole question to every specialist) was used
        because the model's plan was unusable."""
        team = "\n".join(
            f"- {c.name}: {c.description} Skills: " + "; ".join(f"{s.name}: {s.description}" for s in c.skills)
            for c in cards
        )
        prompt = f"""You are the manager of a documentation team. You do not search yourself; you split the user's question into sub-tasks for your specialists.

Your team (from their agent cards):
{team}

Rules:
1. Group the question's asks by the kind of answer they need, and send each specialist at most one sub-task.
2. Send a sub-task only to a specialist that is needed: only exact values -> reference only; only an explanation -> concepts only; both kinds -> both.
3. Make each sub-task self-contained: name the products and settings mentioned in the question.

Question: {question}

Reply with JSON only: {{"sub_tasks": [{{"to": "<specialist name>", "ask": "<sub-task>"}}]}}"""
        text, _ = complete(prompt, json_mode=True)
        names = [c.name for c in cards]
        sub_tasks = parse_plan(text, names)
        if sub_tasks:
            return sub_tasks, False
        return [SubTask(name, question) for name in names], True

    @staticmethod
    def handoff_report(results: List[Tuple[str, str, Task]], handoff: str) -> str:
        """What the specialists hand back, as the manager's prompt sees it. 'findings': one line per finding.
        'full': each specialist's whole conversation, including every search result it read."""
        blocks = []
        for name, ask, task in results:
            if task.state != TaskState.COMPLETED:
                blocks.append(f"{name} could not complete its sub-task \"{ask}\" ({task.status_message}).")
                continue
            if handoff == "full":
                transcript = json.dumps(task.artifact("transcript").get("messages", []), default=str)
                blocks.append(f"Transcript of {name}'s work on \"{ask}\":\n{transcript}")
                continue
            data = task.artifact("findings")
            lines = [f"Findings from {name} (sub-task: \"{ask}\"):"]
            lines += [f"- {f['fact']}" + (f" [{f['source']}]" if f.get("source") else "") for f in data.get("findings", [])]
            if data.get("not_found"):
                lines.append("Not found in the documents: " + "; ".join(data["not_found"]))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def synthesize(self, question: str, report: str) -> str:
        prompt = f"""You are the manager of a documentation team. Your specialists searched the documentation and reported back below. Write the final answer to the user's question from their reports only.
- Answer every part of the question.
- If a part is reported as not found and nothing else covers it, say the documentation does not cover it; do not guess.
- Show any arithmetic.
- Cite sources as [File: filename].

Question: {question}

{report}

Answer:"""
        text, _ = complete(prompt)
        return text
