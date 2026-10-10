"""
The team's two narrow specialists. Each has one search tool, short instructions and a few steps, and hands back
compact findings (one sentence + source each) rather than its whole conversation.

- concepts:  how and why things work (mechanisms, workflows, architecture). Searches by meaning.
- reference: exact facts (numbers, defaults, limits, prices, named lists). Searches by exact keywords (BM25).
"""
import json
import re
import time
from typing import Any, Callable, Dict, List

from app.agents.rag_agent import _compact_for_llm
from app.agents.team.a2a import AgentCard, AgentSkill, Message, Task
from app.agents.tools import exact_keyword_search, semantic_vector_search
from app.services.llm.client import LLMUnavailableError, ToolChat
from app.services.retrieval.excerpts import focus_terms

MAX_SEARCH_STEPS = 3

FINDINGS_FORMAT = (
    "When you are done, reply with JSON only, no other text:\n"
    '{"findings": [{"fact": "<one sentence>", "source": "<filename>#<chunk_index>"}], '
    '"not_found": ["<part of the sub-task the passages do not cover>"]}'
)

CONCEPTS_CARD = AgentCard(
    name="concepts",
    description=(
        "Explains how and why things work in the documentation: mechanisms, workflows, architecture, behaviour, "
        "trade-offs and the reasons behind design choices. Searches by meaning (semantic vector search)."
    ),
    skills=[AgentSkill(
        id="explain-mechanism",
        name="Explain a mechanism",
        description="Explain how a feature, process or architecture works and why, from the documentation.",
        tags=["how", "why", "workflow", "architecture", "comparison"],
        examples=["How does the queue visibility timeout work?", "Why use a cache instead of the database for product data?"],
    )],
)

REFERENCE_CARD = AgentCard(
    name="reference",
    description=(
        "Looks up exact facts in the documentation: numbers, defaults, limits, prices, durations, dates, versions "
        "and named lists (services, roles, regions). Searches by exact keywords (BM25)."
    ),
    skills=[AgentSkill(
        id="lookup-exact-values",
        name="Look up exact values",
        description="Find precise values and names exactly as the documentation states them.",
        tags=["value", "default", "limit", "price", "date", "list"],
        examples=["What is the default visibility timeout?", "How much does Archive storage cost per GB per month?"],
    )],
)

CONCEPTS_INSTRUCTIONS = (
    "You are the Concepts specialist in a documentation team. Your only job: explain how and why things work "
    "(mechanisms, workflows, architecture, behaviour, reasons for design choices) for the sub-task you are given.\n"
    "Search the documentation with semantic_vector_search; rephrase and search again if the results miss part of "
    "the sub-task. Use only what the retrieved passages say. Include a number or limit only if a passage states it.\n"
    + FINDINGS_FORMAT + "\nGive 2 to 6 findings."
)

REFERENCE_INSTRUCTIONS = (
    "You are the Reference specialist in a documentation team. Your only job: find exact facts (numbers, defaults, "
    "limits, prices, durations, dates, versions, and named lists such as services, roles or regions) for the "
    "sub-task you are given.\n"
    "Search with exact_keyword_search using the precise product and setting names; search again with other "
    "keywords if a value is missing. Copy values exactly as written and never guess. If the sub-task needs "
    "arithmetic on values you found, show the calculation.\n"
    + FINDINGS_FORMAT + "\nList every requested value you could not find under not_found."
)


def parse_findings(text: str) -> Dict[str, List[Any]]:
    """The specialist's JSON reply; free text (a model ignoring the format) becomes a single finding."""
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            findings = [f for f in data.get("findings", []) if isinstance(f, dict) and f.get("fact")]
            not_found = [str(n) for n in data.get("not_found", []) if n]
            return {"findings": findings, "not_found": not_found}
        except (json.JSONDecodeError, AttributeError):
            pass
    text = (text or "").strip()
    return {"findings": [{"fact": text, "source": ""}] if text else [], "not_found": []}


class Specialist:
    """A narrow team member reachable through A2A: it receives a sub-task, searches, and returns findings."""

    def __init__(self, card: AgentCard, instructions: str, tool: Callable[..., Dict[str, Any]], max_steps: int = MAX_SEARCH_STEPS):
        self.card = card
        self.instructions = instructions
        self.tool = tool
        self.max_steps = max_steps

    @property
    def name(self) -> str:
        return self.card.name

    def handle(self, task: Task) -> None:
        request = task.history[-1]
        ask = request.text
        document_id = request.data.get("document_id")
        deadline = request.data.get("deadline")
        terms = focus_terms(ask)

        chat = ToolChat(system=self.instructions, user=f"Sub-task: {ask}", tools=[self.tool])
        chunks: Dict[str, Dict[str, Any]] = {}
        searches, final_text = 0, None
        for _ in range(self.max_steps):
            if deadline is not None and time.time() >= deadline:
                break
            try:
                calls, text = chat.step()
            except LLMUnavailableError:
                # Every model failed this turn, e.g. by calling a tool that does not exist. Report from what was
                # found so far; if the LLM is really unavailable, the report below fails too and so does the task.
                break
            if not calls:
                final_text = text
                break
            for call in calls:
                if call.name != self.tool.__name__:
                    result: Dict[str, Any] = {"error": f"Unknown tool '{call.name}'. Use {self.tool.__name__}."}
                else:
                    # The manager decides the scope; the specialist always searches the task's document
                    args = {**call.args, "document_id": document_id}
                    try:
                        result = self.tool(**args)
                        searches += 1
                    except TypeError as err:
                        result = {"error": f"Invalid arguments for '{call.name}': {err}"}
                for chunk in result.get("results", []):
                    chunks[f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"] = chunk
                chat.add_tool_result(call, _compact_for_llm(result, terms))

        if final_text is None:
            # Step budget or time used up, or the model stopped making valid tool calls: report now, without tools
            if not chunks:
                # No search got done: run one with the sub-task itself so the report has evidence to work from
                result = self.tool(query=ask, document_id=document_id)
                searches += 1
                for chunk in result.get("results", []):
                    chunks[f"{chunk.get('doc_id')}_{chunk.get('chunk_index')}"] = chunk
                chat.add_note("Search results for the sub-task:\n" + json.dumps(_compact_for_llm(result, terms), default=str))
            chat.add_note("Your search budget is used up. Report your findings now, as JSON only.")
            _, final_text = chat.step(allow_tools=False)

        findings = parse_findings(final_text)
        task.history.append(Message.build("agent", final_text))
        # findings: what the manager gets. evidence: retrieved chunks, kept for citations only.
        # transcript: the specialist's whole conversation, handed over only in the "full" hand-off ablation.
        task.add_artifact("findings", {**findings, "searches": searches})
        task.add_artifact("evidence", {"chunks": list(chunks.values())})
        task.add_artifact("transcript", {"messages": json.loads(json.dumps(chat.history, default=str))})


def build_specialists() -> List[Specialist]:
    return [
        Specialist(CONCEPTS_CARD, CONCEPTS_INSTRUCTIONS, semantic_vector_search),
        Specialist(REFERENCE_CARD, REFERENCE_INSTRUCTIONS, exact_keyword_search),
    ]
