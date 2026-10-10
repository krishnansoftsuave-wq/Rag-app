"""
Archived documents (docs for old versions, e.g. the SDK 2.x pages) are left out of retrieval unless the user's
question asks about an older version, so an answer cannot copy deprecated code from them (Week 11 drill fix).

The user's question, not the agent's search query, decides: an agent may search "upload file bucket" for a question
that said "we are pinned to 2.x". Each entry point (agent, team, workflow, standard chat) runs inside
question_scope(question); searches made outside one (MCP tools, scripts) only look at their own query.
"""
import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

POLICY = "exclude-archived-v1"  # logged on every retrieval span

LEGACY_PATTERN = re.compile(
    r"(\bv?2\.\d+|\bv?2\.x\b|\bv2\b|version 2\b|sdk 2\b|<\s*3\.0|\blegacy\b|\bolder version|\bold version|"
    r"\bpinned\b|\bcannot upgrade|\bcan't upgrade|\bdeprecated\b|\barchived?\b)",
    re.IGNORECASE,
)

_question: ContextVar[str] = ContextVar("question_for_version_policy", default="")


@contextmanager
def question_scope(question: str) -> Iterator[None]:
    token = _question.set(question or "")
    try:
        yield
    finally:
        _question.reset(token)


def wants_archived(search_query: str) -> bool:
    """True when the user's question (or, outside a question scope, the search query) asks about an older version."""
    return bool(LEGACY_PATTERN.search(f"{_question.get()} {search_query}"))
