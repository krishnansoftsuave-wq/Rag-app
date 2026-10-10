"""
Shared LLM access for the RAG app. An LLM is required: there is no local fallback, so when no model
can answer, callers get an LLMUnavailableError explaining why (missing key, rate limit, overload).

LLM_PROVIDER picks the backend (defaults to "groq" when GROQ_API_KEY is set, otherwise "gemini"):
- groq:   Groq's OpenAI-compatible API. Key from GROQ_API_KEY, models from GROQ_MODELS (in order).
- gemini: Google Gemini. Key from GEMINI_API_KEY.

Every request has a timeout and no hidden SDK retries; calls fall back across the provider's models.
A model that is rate-limited, overloaded, missing or slow is put on a cooldown per key, so later calls
skip it instead of failing on it again.

Token usage: inside `with track_usage() as meter:` every successful call records the token counts the provider
reports (not an estimate), the model that answered and the label set with usage_label(). Meters nest, and the
specialist threads of the agent team copy the caller's context, so their calls land in the same meter.
"""
import os
import re
import json
import time
import typing
import inspect
import hashlib
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from app.core.config import GEMINI_API_KEY, GROQ_API_KEY
from app.core.logger import get_logger
from app.services.llm.pricing import call_cost

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
# "try again in 7m15.3s", "1h2m", "9s", "105ms": duration parts read as (number, unit), "ms" before "m"
_RETRY_HINT = re.compile(r"(?:try again|retry) in\s+((?:[\d.]+(?:ms|h|m|s)\s*)+)", re.IGNORECASE)
_DURATION_PART = re.compile(r"([\d.]+)(ms|h|m|s)", re.IGNORECASE)
_UNIT_SECONDS = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
_MAX_COOLDOWN_SECONDS = 24 * 3600
MAX_COOLDOWN_WAIT_SECONDS = 20  # wait for a model this close to leaving cooldown instead of failing
RATE_LIMIT_RETRIES = 1  # how many times one call waits for a cooldown before failing

_cooldown_until: Dict[str, float] = {}
_last_failure: Dict[str, str] = {}

logger.info(f"LLM provider: {PROVIDER_LABEL} (models: {', '.join(MODELS.get(PROVIDER, []))})")


class LLMUnavailableError(RuntimeError):
    """No model of the configured provider could serve the request."""


def set_models(models: List[str]) -> None:
    """Pin the configured provider to these models (in order), e.g. one model for a fair benchmark race."""
    MODELS[PROVIDER] = list(models)


# ---------------------------------------------------------------------------
# Usage metering
# ---------------------------------------------------------------------------

@dataclass
class LLMCallUsage:
    label: str
    model: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int


class UsageMeter:
    """Provider-reported usage of the LLM calls made while this meter is active, plus time spent waiting
    for rate limits. Thread-safe: parallel specialists add to the same meter."""

    def __init__(self):
        self.calls: List[LLMCallUsage] = []
        self.wait_seconds = 0.0
        self._lock = threading.Lock()

    def add(self, call: LLMCallUsage) -> None:
        with self._lock:
            self.calls.append(call)

    def add_wait(self, seconds: float) -> None:
        with self._lock:
            self.wait_seconds += seconds

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def cached_input_tokens(self) -> int:
        return sum(c.cached_input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def models(self) -> List[str]:
        return sorted({c.model for c in self.calls})

    @property
    def unpriced_models(self) -> List[str]:
        return sorted({c.model for c in self.calls if call_cost(c.model, 0, 0, 0) is None})

    @property
    def cost(self) -> float:
        """USD for the priced calls; see unpriced_models for calls that could not be priced."""
        return sum(call_cost(c.model, c.input_tokens, c.cached_input_tokens, c.output_tokens) or 0.0 for c in self.calls)

    def by_label(self) -> Dict[str, Dict[str, Any]]:
        """Calls, tokens and cost per label (e.g. per agent of a team)."""
        out: Dict[str, Dict[str, Any]] = {}
        for c in self.calls:
            row = out.setdefault(c.label or "unlabelled", {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0})
            row["calls"] += 1
            row["input_tokens"] += c.input_tokens
            row["output_tokens"] += c.output_tokens
            row["cost"] += call_cost(c.model, c.input_tokens, c.cached_input_tokens, c.output_tokens) or 0.0
        return out


_meters: ContextVar[Tuple[UsageMeter, ...]] = ContextVar("llm_usage_meters", default=())
_label: ContextVar[str] = ContextVar("llm_usage_label", default="")


@contextmanager
def track_usage() -> Iterator[UsageMeter]:
    """Record every LLM call made in this context (and in threads started with a copy of it)."""
    meter = UsageMeter()
    token = _meters.set(_meters.get() + (meter,))
    try:
        yield meter
    finally:
        _meters.reset(token)


@contextmanager
def usage_label(label: str) -> Iterator[None]:
    """Tag the LLM calls made in this context, e.g. with the name of the agent making them."""
    token = _label.set(label)
    try:
        yield
    finally:
        _label.reset(token)


def _usage_counts(response: Any) -> Tuple[int, int, int]:
    """(input, cached input, output) tokens as reported by the provider; output includes reasoning tokens."""
    if PROVIDER == "groq":
        usage = getattr(response, "usage", None)
        if not usage:
            return 0, 0, 0
        details = getattr(usage, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
        return usage.prompt_tokens or 0, cached, usage.completion_tokens or 0
    usage = getattr(response, "usage_metadata", None)
    if not usage:
        return 0, 0, 0
    output = (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)
    return usage.prompt_token_count or 0, usage.cached_content_token_count or 0, output


def _metered(model: str, response: Any) -> Any:
    """Record a successful response's usage in every active meter; returns the response unchanged."""
    meters = _meters.get()
    if meters:
        inp, cached, out = _usage_counts(response)
        call = LLMCallUsage(_label.get(), model, inp, cached, out)
        for meter in meters:
            meter.add(call)
    return response


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


def available_models(key: str, models: Optional[List[str]] = None) -> List[str]:
    """The models (default: the provider's) in preference order, minus any cooling down for this key. May be empty."""
    now, kid = time.time(), _key_id(key)
    return [m for m in (models or MODELS.get(PROVIDER, [])) if _cooldown_until.get(f"{kid}:{m}", 0) <= now]


def retry_hint_seconds(message: str) -> Optional[float]:
    """Seconds from a provider's "try again in ..." hint, or None when the message has none."""
    hint = _RETRY_HINT.search(message)
    if not hint:
        return None
    return sum(float(value) * _UNIT_SECONDS[unit.lower()] for value, unit in _DURATION_PART.findall(hint.group(1)))


def _mark_failed(key: str, model: str, err: Exception) -> None:
    message = f"{type(err).__name__}: {err}"
    kid = _key_id(key)
    rule = next(((secs, reason) for marker, secs, reason in _ERROR_RULES if marker in message), None)
    if not rule:
        _last_failure[kid] = f"{model}: {message[:160]}"
        return
    seconds, reason = rule
    hinted = retry_hint_seconds(message)
    if seconds and hinted is not None:
        seconds = min(hinted + 1, _MAX_COOLDOWN_SECONDS)
    if seconds:
        _cooldown_until[f"{kid}:{model}"] = time.time() + seconds
        logger.warning(f"{PROVIDER_LABEL} model {model} cooling down for {int(seconds)}s ({reason})")
    _last_failure[kid] = f"{model}: {reason}"


def _cooldown_waits(key: str, models: Optional[List[str]] = None) -> List[float]:
    """Seconds left on each of these models' cooldowns for this key."""
    kid, now = _key_id(key), time.time()
    return [until - now for m in (models or MODELS.get(PROVIDER, []))
            if (until := _cooldown_until.get(f"{kid}:{m}", 0)) > now]


def _unavailable_error(key: str, models: Optional[List[str]] = None) -> LLMUnavailableError:
    kid = _key_id(key)
    waits = _cooldown_waits(key, models)
    retry = ""
    if len(waits) == len(models or MODELS.get(PROVIDER, [])):
        minutes = int(min(waits) // 60) + 1
        retry = f" Try again in about {minutes} min." if minutes < 120 else f" Try again in about {minutes // 60} hours."
    reason = _last_failure.get(kid, "every model failed")
    return LLMUnavailableError(f"{PROVIDER_LABEL} is unavailable (last error: {reason}).{retry}")


def _with_fallback(call: Callable[[Any, str], Any], models: Optional[List[str]] = None) -> Tuple[Any, str]:
    """Run call(client, model) on the first model (default: the provider's models) that succeeds.
    Returns (result, model)."""
    key = _resolve_key()
    if not key:
        raise LLMUnavailableError(NO_KEY_MESSAGE.get(PROVIDER, f"No API key configured for {PROVIDER_LABEL}."))
    client = _client(key)
    for attempt in range(1 + RATE_LIMIT_RETRIES):
        for model in available_models(key, models):
            try:
                return call(client, model), model
            except Exception as err:
                _mark_failed(key, model, err)
                logger.warning(f"{PROVIDER_LABEL} model {model} failed: {err}")
        # Every model is cooling down. Per-minute rate limits clear within seconds, so wait once for the
        # soonest model instead of failing the request; longer limits (daily caps) fail immediately.
        wait = _soonest_cooldown(key, models)
        if attempt == RATE_LIMIT_RETRIES or wait is None or wait > MAX_COOLDOWN_WAIT_SECONDS:
            break
        logger.info(f"All {PROVIDER_LABEL} models are rate-limited; waiting {wait:.0f}s for the next one")
        time.sleep(wait)
        for meter in _meters.get():
            meter.add_wait(wait)
    raise _unavailable_error(key, models)


def cooldown_remaining(models: Optional[List[str]] = None) -> Optional[float]:
    """Seconds until one of these models (default: the provider's) can be called again after rate limits;
    None if one is available now."""
    return _soonest_cooldown(_resolve_key(), models)


def _soonest_cooldown(key: str, models: Optional[List[str]] = None) -> Optional[float]:
    """Seconds until the first of these models leaves cooldown; None if a model is available or none failed."""
    if available_models(key, models):
        return None
    waits = _cooldown_waits(key, models)
    return min(waits) if waits else None


# ---------------------------------------------------------------------------
# Single-turn completion
# ---------------------------------------------------------------------------

def complete(
    prompt: str,
    json_mode: bool = False,
    models: Optional[List[str]] = None,
    temperature: Optional[float] = None,
) -> Tuple[str, str]:
    """Answer one prompt. Returns (text, model) or raises LLMUnavailableError.
    models overrides the provider's model list (e.g. a separate judge model)."""
    def call(client: Any, model: str) -> str:
        if PROVIDER == "groq":
            extra: Dict[str, Any] = {"response_format": {"type": "json_object"}} if json_mode else {}
            if temperature is not None:
                extra["temperature"] = temperature
            res = _metered(model, client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], **extra))
            text = res.choices[0].message.content
        else:
            config: Dict[str, Any] = {"response_mime_type": "application/json"} if json_mode else {}
            if temperature is not None:
                config["temperature"] = temperature
            text = _metered(model, client.models.generate_content(model=model, contents=prompt, config=config or None)).text
        if not text:
            raise ValueError("empty response")
        return text

    return _with_fallback(call, models)


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
        msg, _ = _with_fallback(lambda client, model: _metered(model, client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            tools=[{"type": "function", "function": t} for t in tools],
            tool_choice="required",
            temperature=0.1,
        )).choices[0].message)
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
    response, _ = _with_fallback(lambda client, model: _metered(model, client.models.generate_content(
        model=model, contents=user, config=config,
    )))
    return [ToolCall(c.id or c.name, c.name, dict(c.args or {})) for c in (response.function_calls or [])]


def _as_plain_chat(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """An OpenAI-style conversation without tool-call structure: tool calls and their results become text turns."""
    plain = []
    for m in history:
        if m.get("role") == "tool":
            plain.append({"role": "user", "content": f"Tool result:\n{m.get('content', '')}"})
        elif m.get("role") == "assistant" and m.get("tool_calls"):
            calls = ", ".join(f"{tc['function']['name']}({tc['function']['arguments']})" for tc in m["tool_calls"])
            plain.append({"role": "assistant", "content": f"{m.get('content') or ''}\nCalled: {calls}".strip()})
        else:
            plain.append(m)
    return plain


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

    def step(self, allow_tools: bool = True) -> Tuple[List[ToolCall], str]:
        """Ask the model for its next move: tool calls to run, or (when there are none) the final answer.
        allow_tools=False forces a final answer, e.g. once a step budget is used up."""
        if PROVIDER == "groq":
            if not allow_tools:
                # Some models still emit a tool call when tool_choice is "none", which Groq rejects (400), so the
                # final turn is plain chat: no tools offered, earlier tool calls and results written out as text
                msg, _ = _with_fallback(lambda client, model: _metered(model, client.chat.completions.create(
                    model=model, messages=_as_plain_chat(self.history), temperature=0.2,
                )).choices[0].message)
                return [], msg.content or ""
            msg, _ = _with_fallback(lambda client, model: _metered(model, client.chat.completions.create(
                model=model, messages=self.history, tools=self._schemas, tool_choice="auto", temperature=0.2,
            )).choices[0].message)
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

        config = self._config
        if not allow_tools:
            from google.genai import types
            config = config.model_copy(update={"tool_config": types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="NONE"))})
        response, _ = _with_fallback(lambda client, model: _metered(model, client.models.generate_content(
            model=model, contents=self.history, config=config,
        )))
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
