"""
Shared LLM access for the RAG app. An LLM is required: there is no local fallback, so when no model
can answer, callers get an LLMUnavailableError explaining why (missing key, rate limit, overload).

LLM_PROVIDER picks the backend (defaults to "groq" when GROQ_API_KEY is set, otherwise "gemini"):
- groq:   Groq's OpenAI-compatible API. Key from GROQ_API_KEY, models from GROQ_MODELS (in order).
- gemini: Google Gemini. Key from GEMINI_API_KEY.

Every request has a timeout and no hidden SDK retries; calls fall back across the provider's models.
A model that is rate-limited, overloaded, missing or slow is put on a cooldown per key, so later calls
skip it instead of failing on it again.
"""
import os
import re
import json
import time
import typing
import inspect
import hashlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.config import GEMINI_API_KEY, GROQ_API_KEY
from app.core.logger import get_logger

logger = get_logger("llm_client")

PROVIDER = (os.getenv("LLM_PROVIDER") or ("groq" if GROQ_API_KEY else "gemini")).strip().lower()
PROVIDER_LABEL = {"groq": "Groq", "gemini": "Gemini"}.get(PROVIDER, PROVIDER)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "20"))

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODELS = {
    "groq": [m.strip() for m in os.getenv("GROQ_MODELS", "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b").split(",") if m.strip()],
    "gemini": ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"],
}
NO_KEY_MESSAGE = {
    "groq": "No Groq API key configured. Set GROQ_API_KEY in backend/.env and restart the backend.",
    "gemini": "No Gemini API key configured. Set GEMINI_API_KEY in backend/.env and restart the backend.",
}

# (marker found in the error text, cooldown seconds, readable reason). A "try again in ..." hint in the
# error text replaces the cooldown; 0 means remember the reason without cooling the model down.
_ERROR_RULES = [
    # 413: this one request exceeds the model's per-minute token cap; the model is not rate-limited, try the next
    ("Request too large", 0, "request too large for the model's tokens-per-minute limit (413)"),
    ("RESOURCE_EXHAUSTED", 300, "quota exceeded (429)"),
    ("rate_limit", 60, "rate limit reached (429)"),
    ("429", 120, "rate limit reached (429)"),
    ("UNAVAILABLE", 60, "model overloaded (503)"),
    ("503", 60, "model overloaded (503)"),
    ("model_not_found", 3600, "model not found (404)"),
    ("does not exist", 3600, "model not found (404)"),
    ("NOT_FOUND", 3600, "model not found (404)"),
    ("404", 3600, "model not found (404)"),
    ("timed out", 60, "request timed out"),
    ("Timeout", 60, "request timed out"),
    ("invalid_api_key", 0, "invalid API key (401)"),
    ("API key not valid", 0, "invalid API key"),
    ("401", 0, "invalid API key (401)"),
]
_RETRY_HINT = re.compile(r"(?:try again|retry) in\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", re.IGNORECASE)
_MAX_COOLDOWN_SECONDS = 24 * 3600
MAX_COOLDOWN_WAIT_SECONDS = 20  # wait for a model this close to leaving cooldown instead of failing

_cooldown_until: Dict[str, float] = {}
_last_failure: Dict[str, str] = {}

logger.info(f"LLM provider: {PROVIDER_LABEL} (models: {', '.join(MODELS.get(PROVIDER, []))})")


class LLMUnavailableError(RuntimeError):
    """No model of the configured provider could serve the request."""


# ---------------------------------------------------------------------------
# Keys, clients, cooldowns
# ---------------------------------------------------------------------------

def _resolve_key() -> str:
    return GROQ_API_KEY if PROVIDER == "groq" else GEMINI_API_KEY


def _key_id(key: str) -> str:
    return f"{PROVIDER}:{hashlib.sha256((key or '').encode()).hexdigest()[:12]}"


@lru_cache(maxsize=8)
def _client(key: str) -> Any:
    if PROVIDER == "groq":
        from openai import OpenAI
        return OpenAI(api_key=key, base_url=GROQ_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)
    from google import genai
    from google.genai import types
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=int(REQUEST_TIMEOUT_SECONDS * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def available_models(key: str) -> List[str]:
    """The provider's models in preference order, minus any cooling down for this key. May be empty."""
    now, kid = time.time(), _key_id(key)
    return [m for m in MODELS.get(PROVIDER, []) if _cooldown_until.get(f"{kid}:{m}", 0) <= now]


def _mark_failed(key: str, model: str, err: Exception) -> None:
    message = f"{type(err).__name__}: {err}"
    kid = _key_id(key)
    rule = next(((secs, reason) for marker, secs, reason in _ERROR_RULES if marker in message), None)
    if not rule:
        _last_failure[kid] = f"{model}: {message[:160]}"
        return
    seconds, reason = rule
    hint = _RETRY_HINT.search(message)
    if seconds and hint and any(hint.groups()):
        h, m, s = hint.groups()
        seconds = min(int(h or 0) * 3600 + int(m or 0) * 60 + float(s or 0) + 1, _MAX_COOLDOWN_SECONDS)
    if seconds:
        _cooldown_until[f"{kid}:{model}"] = time.time() + seconds
        logger.warning(f"{PROVIDER_LABEL} model {model} cooling down for {int(seconds)}s ({reason})")
    _last_failure[kid] = f"{model}: {reason}"


def _unavailable_error(key: str) -> LLMUnavailableError:
    kid, now = _key_id(key), time.time()
    waits = [until - now for k, until in _cooldown_until.items() if k.startswith(f"{kid}:") and until > now]
    retry = ""
    if len(waits) == len(MODELS.get(PROVIDER, [])):
        minutes = int(min(waits) // 60) + 1
        retry = f" Try again in about {minutes} min." if minutes < 120 else f" Try again in about {minutes // 60} hours."
    reason = _last_failure.get(kid, "every model failed")
    return LLMUnavailableError(f"{PROVIDER_LABEL} is unavailable (last error: {reason}).{retry}")


def _with_fallback(call: Callable[[Any, str], Any]) -> Tuple[Any, str]:
    """Run call(client, model) on the first model that succeeds. Returns (result, model)."""
    key = _resolve_key()
    if not key:
        raise LLMUnavailableError(NO_KEY_MESSAGE.get(PROVIDER, f"No API key configured for {PROVIDER_LABEL}."))
    client = _client(key)
    for attempt in range(2):
        for model in available_models(key):
            try:
                return call(client, model), model
            except Exception as err:
                _mark_failed(key, model, err)
                logger.warning(f"{PROVIDER_LABEL} model {model} failed: {err}")
        # Every model is cooling down. Per-minute rate limits clear within seconds, so wait once for the
        # soonest model instead of failing the request; longer limits (daily caps) fail immediately.
        wait = _soonest_cooldown(key)
        if attempt or wait is None or wait > MAX_COOLDOWN_WAIT_SECONDS:
            break
        logger.info(f"All {PROVIDER_LABEL} models are rate-limited; waiting {wait:.0f}s for the next one")
        time.sleep(wait)
    raise _unavailable_error(key)


def _soonest_cooldown(key: str) -> Optional[float]:
    """Seconds until the first of this key's models leaves cooldown; None if a model is available or none failed."""
    if available_models(key):
        return None
    kid, now = _key_id(key), time.time()
    waits = [until - now for k, until in _cooldown_until.items() if k.startswith(f"{kid}:") and until > now]
    return min(waits) if waits else None


# ---------------------------------------------------------------------------
# Single-turn completion
# ---------------------------------------------------------------------------

def complete(prompt: str, json_mode: bool = False) -> Tuple[str, str]:
    """Answer one prompt. Returns (text, model) or raises LLMUnavailableError."""
    def call(client: Any, model: str) -> str:
        if PROVIDER == "groq":
            extra = {"response_format": {"type": "json_object"}} if json_mode else {}
            res = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], **extra)
            text = res.choices[0].message.content
        else:
            config = {"response_mime_type": "application/json"} if json_mode else None
            text = client.models.generate_content(model=model, contents=prompt, config=config).text
        if not text:
            raise ValueError("empty response")
        return text

    return _with_fallback(call)


# ---------------------------------------------------------------------------
# Tool-calling conversation (used by the agent)
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _tool_schema(fn: Callable) -> Dict[str, Any]:
    """OpenAI-style function schema built from a tool's signature and docstring."""
    hints = typing.get_type_hints(fn)
    properties, required = {}, []
    for name, param in inspect.signature(fn).parameters.items():
        hint = hints.get(name, str)
        inner = [a for a in typing.get_args(hint) if a is not type(None)]
        base = inner[0] if typing.get_origin(hint) is typing.Union and inner else hint
        properties[name] = {"type": _JSON_TYPES.get(base, "string")}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    doc = inspect.getdoc(fn) or fn.__name__
    described = re.search(r"Description:\s*(.+)", doc)
    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": (described.group(1) if described else doc.splitlines()[0]).strip(),
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _parse_args(raw: Optional[str]) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def choose_tool_call(system: str, user: str, tools: List[Dict[str, Any]]) -> List[ToolCall]:
    """One forced tool-choice turn: the model must call one of the given tools (already-described as
    {"name", "description", "parameters": <JSON schema>}, e.g. tools listed by an MCP server). Returns its calls."""
    if PROVIDER == "groq":
        msg, _ = _with_fallback(lambda client, model: client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            tools=[{"type": "function", "function": t} for t in tools],
            tool_choice="required",
            temperature=0.1,
        ).choices[0].message)
        return [ToolCall(tc.id, tc.function.name, _parse_args(tc.function.arguments)) for tc in (msg.tool_calls or [])]

    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=[
            types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["parameters"])
            for t in tools
        ])],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY")),
        temperature=0.1,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response, _ = _with_fallback(lambda client, model: client.models.generate_content(
        model=model, contents=user, config=config,
    ))
    return [ToolCall(c.id or c.name, c.name, dict(c.args or {})) for c in (response.function_calls or [])]


class ToolChat:
    """Provider-neutral tool-calling conversation. The caller runs the tools and reports results back.
    Tools are Python functions; their schema is built from the signature and docstring."""

    def __init__(self, system: str, user: str, tools: List[Callable]):
        if PROVIDER == "groq":
            self.history: List[Any] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            self._schemas = [_tool_schema(fn) for fn in tools]
        else:
            from google.genai import types
            self.history = [types.Content(role="user", parts=[types.Part.from_text(text=user)])]
            self._config = types.GenerateContentConfig(
                system_instruction=system,
                tools=tools,
                temperature=0.2,
                # Tool calls are run by the caller (not inside the SDK) so evidence, budgets and the trace are recorded
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

    def step(self) -> Tuple[List[ToolCall], str]:
        """Ask the model for its next move: tool calls to run, or (when there are none) the final answer."""
        if PROVIDER == "groq":
            msg, _ = _with_fallback(lambda client, model: client.chat.completions.create(
                model=model, messages=self.history, tools=self._schemas, tool_choice="auto", temperature=0.2,
            ).choices[0].message)
            if not msg.tool_calls:
                return [], msg.content or ""
            self.history.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            return [ToolCall(tc.id, tc.function.name, _parse_args(tc.function.arguments)) for tc in msg.tool_calls], ""

        response, _ = _with_fallback(lambda client, model: client.models.generate_content(
            model=model, contents=self.history, config=self._config,
        ))
        calls = response.function_calls or []
        if not calls:
            return [], response.text or ""
        self.history.append(response.candidates[0].content)
        return [ToolCall(c.id or c.name, c.name, dict(c.args or {})) for c in calls], ""

    def add_note(self, text: str) -> None:
        """Give the model context for its next turn, e.g. what an MCP tool already produced for the user."""
        if PROVIDER == "groq":
            self.history.append({"role": "user", "content": text})
        else:
            from google.genai import types
            self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))

    def add_tool_result(self, call: ToolCall, result: Any) -> None:
        if PROVIDER == "groq":
            self.history.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)})
        else:
            from google.genai import types
            self.history.append(types.Content(
                role="tool",
                parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
            ))
