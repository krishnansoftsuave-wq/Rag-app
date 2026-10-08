"""External MCP servers in the RAG agent, used in three stages:

1. select_mcp_server: the LLM sees only the question and the active servers' descriptions (no tools) and
   decides whether the request needs an MCP server, and which one.
2. load_server_tools: the backend connects to the chosen server now and lists its tools over MCP.
3. Those tools are given to the agent's LLM, which calls one; run_agent_tool executes the call. Parameters
   listed in CONTEXT_PARAMS are filled by the backend from the chat context (e.g. the retrieved passages)
   instead of being written by the model, which keeps tool calls small and grounded.
"""
import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Coroutine, Dict, List, Optional, Set, Tuple

from app.core.logger import get_logger
from app.mcp.client.manager import mcp_client_manager
from app.services.llm.client import complete

logger = get_logger("mcp_agent_tools")

CONTEXT_PARAMS = {"sources", "answer"}
MAX_RESULT_CHARS_FOR_LLM = 1500
_VALID_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

SELECT_SERVER_PROMPT = """You route requests in a document Q&A app. Questions are answered by searching the
user's documents. Some requests also need an external MCP server (a service with its own tools).

Available MCP servers:
{servers}

User request: {question}

Does fulfilling this request need one of these servers? Choose a server only when the request asks for what
that server provides; plain questions about the documents need none.
Respond in JSON: {{"server_id": "<id from the list, or null>", "reason": "<one short sentence>"}}"""


@dataclass
class McpAgentTool:
    name: str  # name the LLM sees, unique among the agent's tools
    server_id: str
    server_name: str
    tool_name: str  # name on the MCP server
    description: str
    parameters: Dict[str, Any]
    context_params: Set[str] = field(default_factory=set)

    @property
    def declaration(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}


def _run_sync(coro: Coroutine) -> Any:
    """Run a coroutine from sync code, also when this thread already runs an event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ---------------------------------------------------------------------------
# Stage 1: does this request need an MCP server, and which one?
# ---------------------------------------------------------------------------

def select_mcp_server(question: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """Ask the LLM which active MCP server (if any) the request needs. Returns (server or None, reason)."""
    servers = mcp_client_manager.active_servers()
    if not servers:
        return None, "no MCP servers are enabled"
    listing = "\n".join(
        f"- id: {srv['id']} | name: {srv['name']} | provides: {mcp_client_manager.describe(srv) or '(no description)'}"
        for srv in servers
    )
    text, _ = complete(SELECT_SERVER_PROMPT.format(servers=listing, question=question), json_mode=True)
    try:
        decision = json.loads(text)
    except json.JSONDecodeError:
        return None, f"unreadable routing decision: {text[:120]}"
    chosen = next((srv for srv in servers if srv["id"] == decision.get("server_id")), None)
    return chosen, str(decision.get("reason") or "")


# ---------------------------------------------------------------------------
# Stage 2: connect to the chosen server and list its tools
# ---------------------------------------------------------------------------

def load_server_tools(server: Dict[str, Any], reserved_names: Set[str]) -> Tuple[List[McpAgentTool], Optional[str]]:
    """Connect to the server now and turn its tools into agent tools. Returns (tools, error)."""
    srv = _run_sync(mcp_client_manager.refresh_server(server["id"]))
    if not srv or srv.get("status") != "connected":
        return [], (srv or {}).get("error_detail") or "connection failed"

    tools, taken = [], set(reserved_names)
    for t in srv.get("discovered_tools", []):
        schema = t.get("input_schema") or {}
        properties = dict(schema.get("properties") or {})
        context = {p for p in properties if p in CONTEXT_PARAMS}
        name = t["name"]
        if name in taken or not _VALID_TOOL_NAME.match(name):
            name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"mcp_{srv['id']}_{t['name']}")[:64]
        taken.add(name)
        tools.append(McpAgentTool(
            name=name,
            server_id=srv["id"],
            server_name=srv["name"],
            tool_name=t["name"],
            description=t.get("description") or "",
            parameters={
                "type": "object",
                "properties": {k: v for k, v in properties.items() if k not in context},
                "required": [r for r in schema.get("required", []) if r not in context],
            },
            context_params=context,
        ))
    return tools, None


# ---------------------------------------------------------------------------
# Stage 3: run the tool the LLM chose
# ---------------------------------------------------------------------------

def run_agent_tool(tool: McpAgentTool, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Call the MCP tool with the model's arguments plus the backend-filled context parameters."""
    call_args = {**args, **{p: context[p] for p in tool.context_params if p in context}}
    return _run_sync(mcp_client_manager.call_remote_tool(tool.server_id, tool.tool_name, call_args))


def is_artifact(result: Any) -> bool:
    return isinstance(result, dict) and "type" in result and "data" in result


def summarize_for_llm(response: Dict[str, Any]) -> Dict[str, Any]:
    """What the agent's LLM sees after an MCP call. Artifacts go to the user, so the model only gets a short note."""
    if not response.get("success"):
        return {"error": response.get("error") or "MCP tool call failed."}
    result = response.get("result")
    if is_artifact(result):
        kind = str(result.get("type") or "artifact").replace("_", " ")
        return {
            "status": "created",
            "artifact_type": result.get("type"),
            "title": result.get("title"),
            "note": f"The user sees this {kind} as a card under your answer. Refer to it in one short sentence "
                    f"(e.g. 'See the {kind} below.'); do not draw it, add a placeholder for it, or repeat its contents.",
        }
    text = result if isinstance(result, str) else json.dumps(result, default=str)
    return {"result": text[:MAX_RESULT_CHARS_FOR_LLM]}
