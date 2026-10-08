import os
import json
import uuid
import asyncio
import threading
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from mcp import ClientSession
from mcp.client.sse import sse_client
from app.core.config import DATA_DIR

# Path to store saved MCP external server configurations
SERVERS_FILE = os.path.join(DATA_DIR, "external_mcp_servers.json")

# Saved to SERVERS_FILE: what the user configured, plus the server's own description ("instructions"), which chat
# needs to route a question to a server before connecting to it. Connection results (status, tools) stay in memory
# and are re-read from the server on every test or refresh.
CONFIG_FIELDS = ("id", "name", "description", "instructions", "url", "transport", "auth_type", "auth_token", "is_active")
FIRST_CHECK_TIMEOUT_SECONDS = 10


class MCPClientManager:
    """
    MCP Client Engine: Connects to external custom MCP servers (via SSE or HTTP),
    discovers exported tools, tests connection health, and invokes remote tools.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._save_lock = threading.Lock()  # chat runs MCP calls on worker threads
        self._load_servers()

    def _load_servers(self):
        """Load external server configurations from JSON file."""
        saved = None
        if os.path.exists(SERVERS_FILE):
            try:
                with open(SERVERS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
            except Exception as e:
                print(f"[MCP Client] Error loading servers config: {e}")

        needs_save = saved is None
        if saved is None:
            # Default initial server configuration pointing to Standalone MCP Server
            saved = {
                "srv_standalone_1": {
                    "id": "srv_standalone_1",
                    "name": "Standalone External MCP Server",
                    "url": "http://localhost:8005/sse",
                    "transport": "sse",
                    "auth_type": "none",
                    "auth_token": "",
                    "is_active": True
                }
            }

        self.servers = {
            server_id: {
                **{k: v for k, v in cfg.items() if k in CONFIG_FIELDS},
                # Unknown until the backend connects to the server
                "status": "disconnected",
                "last_tested": None,
                "error_detail": None,
                "discovered_tools": []
            }
            for server_id, cfg in saved.items()
        }
        # Also rewrites a file from an older version that still holds connection results
        if needs_save or saved != self._saved_config():
            self._save_servers()

    def _saved_config(self) -> Dict[str, Dict[str, Any]]:
        """The part of each server entry that is saved to the file."""
        return {sid: {k: srv[k] for k in CONFIG_FIELDS if k in srv} for sid, srv in list(self.servers.items())}

    def _save_servers(self):
        """Save server configurations (CONFIG_FIELDS only) to JSON file."""
        with self._save_lock:
            try:
                with open(SERVERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self._saved_config(), f, indent=2)
            except Exception as e:
                print(f"[MCP Client] Error saving servers config: {e}")

    def list_servers(self) -> List[Dict[str, Any]]:
        """Return list of all configured external MCP servers."""
        return list(self.servers.values())

    @staticmethod
    def public_view(srv: Dict[str, Any]) -> Dict[str, Any]:
        """A server entry as the API returns it: the auth token is never sent back, only whether one is set."""
        view = {k: v for k, v in srv.items() if k != "auth_token"}
        view["has_auth_token"] = bool(srv.get("auth_token"))
        return view

    async def test_server_connection(
        self,
        url: str,
        transport: str = "sse",
        auth_type: str = "none",
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Connect to a custom MCP server URL, perform JSON-RPC handshake over SSE or HTTP,
        and retrieve all exported tools.
        """
        headers = {}
        if auth_type == "bearer" and auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "api_key" and auth_token:
            headers["X-API-Key"] = auth_token

        discovered_tools = []
        status = "error"
        error_msg = None
        instructions = None

        if transport == "sse" or "sse" in url.lower():
            try:
                # Append token to URL if bearer token given for query param fallback
                connect_url = url
                if auth_token and "token=" not in connect_url and auth_type == "bearer":
                    sep = "&" if "?" in connect_url else "?"
                    connect_url = f"{connect_url}{sep}token={auth_token}"

                async with sse_client(connect_url, headers=headers if headers else None) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        init = await session.initialize()
                        # The server's own description of what it is for (used to decide when to use it)
                        server_info = getattr(init, "server_info", None)
                        instructions = getattr(init, "instructions", None) or getattr(server_info, "description", None)
                        tools_res = await session.list_tools()
                        for t in tools_res.tools:
                            discovered_tools.append({
                                "name": t.name,
                                "description": t.description or "No description provided.",
                                # mcp>=2 renamed inputSchema -> input_schema (the old name still works but warns)
                                "input_schema": (t.input_schema if hasattr(t, "input_schema") else getattr(t, "inputSchema", None)) or {}
                            })
                        status = "connected"
            except Exception as err:
                error_msg = f"SSE Connection failed: {str(err)}"
        else:
            # Fallback to HTTP REST / JSON-RPC endpoint test
            try:
                async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        tools = data.get("tools", [])
                        for t in tools:
                            discovered_tools.append({
                                "name": t.get("name"),
                                "description": t.get("description", ""),
                                "input_schema": t.get("parameters", {})
                            })
                        status = "connected"
                    else:
                        error_msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as err:
                error_msg = f"HTTP connection failed: {str(err)}"

        return {
            "status": status,
            "error": error_msg,
            "instructions": instructions,
            "total_tools": len(discovered_tools),
            "tools": discovered_tools,
            "tested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    async def add_server(
        self,
        name: str,
        url: str,
        transport: str = "sse",
        auth_type: str = "none",
        auth_token: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new custom MCP server and discover its tools."""
        server_id = f"srv_{uuid.uuid4().hex[:8]}"

        # Test connection first
        test_res = await self.test_server_connection(url, transport, auth_type, auth_token)

        server_entry = {
            "id": server_id,
            "name": name,
            "description": description or "",  # set by the user; the server's own description is in "instructions"
            "instructions": test_res.get("instructions") or "",
            "url": url,
            "transport": transport,
            "auth_type": auth_type,
            "auth_token": auth_token or "",
            "is_active": True,
            "status": test_res["status"],
            "last_tested": test_res["tested_at"],
            "discovered_tools": test_res["tools"],
            "error_detail": test_res.get("error")
        }

        self.servers[server_id] = server_entry
        self._save_servers()
        return server_entry

    async def refresh_server(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Connect to a configured server now, re-read its description and tool list, and update the registry."""
        srv = self.servers.get(server_id)
        if not srv:
            return None
        test_res = await self.test_server_connection(
            url=srv["url"],
            transport=srv.get("transport", "sse"),
            auth_type=srv.get("auth_type", "none"),
            auth_token=srv.get("auth_token", "")
        )
        srv["status"] = test_res["status"]
        srv["last_tested"] = test_res["tested_at"]
        srv["error_detail"] = test_res.get("error")
        if test_res["status"] == "connected":
            srv["discovered_tools"] = test_res["tools"]
            instructions = test_res.get("instructions") or ""
            # Status and tools stay in memory, so the file is written only when the server's description changed
            if instructions != srv.get("instructions"):
                srv["instructions"] = instructions
                self._save_servers()
        return srv

    async def check_untested_servers(self) -> None:
        """Connect once to each active server not checked since the backend started, so its status and tools are known."""
        async def check(srv: Dict[str, Any]) -> None:
            try:
                await asyncio.wait_for(self.refresh_server(srv["id"]), FIRST_CHECK_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                srv["status"] = "error"
                srv["last_tested"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                srv["error_detail"] = f"No answer within {FIRST_CHECK_TIMEOUT_SECONDS}s"

        await asyncio.gather(*(check(srv) for srv in self.active_servers() if not srv.get("last_tested")))

    def active_servers(self) -> List[Dict[str, Any]]:
        """Servers the user has enabled, whatever their last connection status (it may have changed since)."""
        return [srv for srv in self.servers.values() if srv.get("is_active")]

    @staticmethod
    def describe(srv: Dict[str, Any]) -> str:
        """What a server is for: the user's description, else the server's own MCP instructions."""
        return (srv.get("description") or srv.get("instructions") or "").strip()

    def toggle_server(self, server_id: str, is_active: bool) -> Optional[Dict[str, Any]]:
        """Toggle an MCP server between active/inactive status."""
        if server_id in self.servers:
            self.servers[server_id]["is_active"] = is_active
            self._save_servers()
            return self.servers[server_id]
        return None

    def delete_server(self, server_id: str) -> bool:
        """Remove a custom MCP server entry."""
        if server_id in self.servers:
            del self.servers[server_id]
            self._save_servers()
            return True
        return False

    async def call_remote_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke a tool on a connected remote MCP server."""
        server = self.servers.get(server_id)
        if not server:
            return {"success": False, "error": f"Server '{server_id}' not found."}

        url = server["url"]
        transport = server.get("transport", "sse")
        auth_type = server.get("auth_type", "none")
        auth_token = server.get("auth_token", "")

        headers = {}
        if auth_type == "bearer" and auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "api_key" and auth_token:
            headers["X-API-Key"] = auth_token

        if transport == "sse" or "sse" in url.lower():
            try:
                connect_url = url
                if auth_token and "token=" not in connect_url and auth_type == "bearer":
                    sep = "&" if "?" in connect_url else "?"
                    connect_url = f"{connect_url}{sep}token={auth_token}"

                async with sse_client(connect_url, headers=headers if headers else None) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        
                        # Process response text
                        output_text = ""
                        if result and hasattr(result, "content") and result.content:
                            output_text = getattr(result.content[0], "text", "") or ""
                        # mcp>=2 renamed isError -> is_error (the old name still works but warns)
                        is_error = result.is_error if hasattr(result, "is_error") else getattr(result, "isError", False)
                        if is_error:
                            return {"success": False, "error": output_text or f"Tool '{tool_name}' reported an error."}
                        if output_text:
                            try:
                                parsed = json.loads(output_text)
                                return {"success": True, "result": parsed, "raw": output_text}
                            except Exception:
                                pass
                        return {"success": True, "result": output_text or str(result)}
            except Exception as err:
                return {"success": False, "error": f"Failed to execute tool '{tool_name}' on remote server: {str(err)}"}
        else:
            # REST / HTTP tool execution fallback
            call_url = f"{url.rstrip('/')}/tools/call"
            try:
                async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
                    resp = await client.post(call_url, json={"name": tool_name, "arguments": arguments})
                    if resp.status_code == 200:
                        return {"success": True, "result": resp.json()}
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            except Exception as err:
                return {"success": False, "error": f"HTTP tool execution failed: {str(err)}"}

    def get_all_active_tools(self) -> List[Dict[str, Any]]:
        """Return list of all available tools across all active connected MCP servers."""
        active_tools = []
        for srv in self.servers.values():
            if srv.get("is_active") and srv.get("status") == "connected":
                for t in srv.get("discovered_tools", []):
                    active_tools.append({
                        "server_id": srv["id"],
                        "server_name": srv["name"],
                        "name": t["name"],
                        "description": t["description"],
                        "input_schema": t.get("input_schema", {})
                    })
        return active_tools


# Global singleton instance
mcp_client_manager = MCPClientManager()
