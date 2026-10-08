import os
import json
import uuid
import asyncio
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime
from mcp import ClientSession
from mcp.client.sse import sse_client
from app.core.config import DATA_DIR

# Path to store saved MCP external server configurations
SERVERS_FILE = os.path.join(DATA_DIR, "external_mcp_servers.json")


class MCPClientManager:
    """
    MCP Client Engine: Connects to external custom MCP servers (via SSE or HTTP),
    discovers exported tools, tests connection health, and invokes remote tools.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._load_servers()

    def _load_servers(self):
        """Load external server configurations from JSON file."""
        if os.path.exists(SERVERS_FILE):
            try:
                with open(SERVERS_FILE, "r", encoding="utf-8") as f:
                    self.servers = json.load(f)
                    return
            except Exception as e:
                print(f"[MCP Client] Error loading servers config: {e}")
        
        # Default initial server configuration pointing to Standalone MCP Server
        self.servers = {
            "srv_standalone_1": {
                "id": "srv_standalone_1",
                "name": "Standalone External MCP Server",
                "url": "http://localhost:8005/sse",
                "transport": "sse",
                "auth_type": "none",
                "auth_token": "",
                "is_active": True,
                "status": "disconnected",
                "last_tested": None,
                "discovered_tools": []
            }
        }
        self._save_servers()

    def _save_servers(self):
        """Save server configurations to JSON file."""
        try:
            with open(SERVERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.servers, f, indent=2)
        except Exception as e:
            print(f"[MCP Client] Error saving servers config: {e}")

    def list_servers(self) -> List[Dict[str, Any]]:
        """Return list of all configured external MCP servers."""
        return list(self.servers.values())

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

        if transport == "sse" or "sse" in url.lower():
            try:
                # Append token to URL if bearer token given for query param fallback
                connect_url = url
                if auth_token and "token=" not in connect_url and auth_type == "bearer":
                    sep = "&" if "?" in connect_url else "?"
                    connect_url = f"{connect_url}{sep}token={auth_token}"

                async with sse_client(connect_url, headers=headers if headers else None) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
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
        auth_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new custom MCP server and discover its tools."""
        server_id = f"srv_{uuid.uuid4().hex[:8]}"
        
        # Test connection first
        test_res = await self.test_server_connection(url, transport, auth_type, auth_token)

        server_entry = {
            "id": server_id,
            "name": name,
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

    def find_server_with_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Return the first active, connected server that exposes the given tool."""
        for srv in self.servers.values():
            if srv.get("is_active") and srv.get("status") == "connected":
                if any(t.get("name") == tool_name for t in srv.get("discovered_tools", [])):
                    return srv
        return None

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
