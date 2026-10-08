from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from app.mcp.client.manager import mcp_client_manager
from app.schemas.mcp import AddServerRequest, TestConnectionRequest, CallToolRequest

router = APIRouter()


@router.get("/external-servers")
async def list_external_mcp_servers():
    """List all configured external standalone MCP servers and their discovered tools."""
    # Status and tools are kept in memory only: connect once to servers not checked since the backend started
    await mcp_client_manager.check_untested_servers()
    servers = [mcp_client_manager.public_view(srv) for srv in mcp_client_manager.list_servers()]
    active_tools = mcp_client_manager.get_all_active_tools()
    return {
        "success": True,
        "total_servers": len(servers),
        "servers": servers,
        "active_tools_count": len(active_tools),
        "active_tools": active_tools
    }


@router.post("/external-servers/test")
async def test_mcp_server_connection(req: TestConnectionRequest):
    """Test connection to a custom MCP server URL and discover exported tools without saving."""
    res = await mcp_client_manager.test_server_connection(
        url=req.url,
        transport=req.transport or "sse",
        auth_type=req.auth_type or "none",
        auth_token=req.auth_token
    )
    return res


@router.post("/external-servers")
async def add_external_mcp_server(req: AddServerRequest):
    """Add a new custom MCP server to the application client registry."""
    if not req.name or not req.url:
        raise HTTPException(status_code=400, detail="Server name and URL are required.")

    server_entry = await mcp_client_manager.add_server(
        name=req.name,
        url=req.url,
        transport=req.transport or "sse",
        auth_type=req.auth_type or "none",
        auth_token=req.auth_token,
        description=req.description
    )
    return {"success": True, "server": mcp_client_manager.public_view(server_entry)}


@router.post("/external-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, payload: Dict[str, Any] = Body(...)):
    """Enable or disable an external MCP server."""
    is_active = payload.get("is_active", True)
    updated = mcp_client_manager.toggle_server(server_id, is_active)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return {"success": True, "server": mcp_client_manager.public_view(updated)}


@router.post("/external-servers/{server_id}/refresh")
async def refresh_mcp_server(server_id: str):
    """Refresh health check and re-discover tools for a configured MCP server."""
    srv = await mcp_client_manager.refresh_server(server_id)
    if not srv:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return {"success": True, "server": mcp_client_manager.public_view(srv)}


@router.delete("/external-servers/{server_id}")
async def delete_mcp_server(server_id: str):
    """Remove a custom MCP server configuration."""
    deleted = mcp_client_manager.delete_server(server_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Server '{server_id}' not found.")
    return {"success": True, "message": f"Server '{server_id}' removed successfully."}


@router.post("/external-servers/call-tool")
async def call_remote_mcp_tool(req: CallToolRequest):
    """Directly invoke a tool on a connected remote MCP server."""
    result = await mcp_client_manager.call_remote_tool(
        server_id=req.server_id,
        tool_name=req.tool_name,
        arguments=req.arguments or {}
    )
    return result
